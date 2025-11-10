
"""
Piyavskiy method for global optimization.
- Принимает строковое представление функции f(x) (например "x + sin(3.14159*x)"),
  отрезок [a,b], точность eps.
- Оценивает константу Липшица L (по дискретной выборке производной или при отсутствии - по разностям).
- Строит минoранту (ломаную) и последовательно добавляет точки, находя глобальный минимум.
- Выводит график исходной функции, текущей ломаной (minorant), точки выборов,
  итоговую аппроксимацию минимума, число итераций и время выполнения.
"""

import time
import math
import numpy as np
import matplotlib.pyplot as plt
from typing import Callable, Tuple, List, Optional

try:
    import sympy as sp
    _HAS_SYM = True
except Exception:
    _HAS_SYM = False

def make_function_from_string(expr: str) -> Callable[[float], float]:
    """
    Преобразует строку с функцией в callable f(x).
    Примеры ввода: "x + sin(3.14159*x)", "x**2 + 10 - 10*cos(2*pi*x)"
    Поддерживаемые имена: sin, cos, tan, exp, log, sqrt, pi, e, abs, etc.
    """
    # Простая безопасная среда выполнения
    import math as _math
    allowed_names = {
        k: getattr(_math, k) for k in [
            'sin','cos','tan','asin','acos','atan','sinh','cosh','tanh',
            'exp','log','log10','sqrt','fabs','floor','ceil','pow'
        ] if hasattr(_math, k)
    }
    allowed_names.update({
        'pi': math.pi,
        'e': math.e,
        'abs': abs,
        'min': min,
        'max': max
    })

    # Убираем "f(x) = ..." если есть
    if '=' in expr:
        _, rhs = expr.split('=', 1)
        expr = rhs.strip()

    # Нужная функция
    def f(x: float) -> float:
        # Локальная переменная x доступна в eval
        local_dict = {'x': float(x)}
        return float(eval(expr, {"__builtins__": {}}, {**allowed_names, **local_dict}))
    return f


def estimate_lipschitz_constant(f: Callable[[float], float],
                                a: float, b: float,
                                n_samples: int = 1000,
                                use_sympy: bool = True,
                                sympy_expr: Optional[str] = None) -> float:
    """
    Попытаться оценить L (константы Липшица)
    """
    L = 0.0
    if _HAS_SYM and use_sympy and sympy_expr is not None:
        try:
            x = sp.symbols('x')
            parsed = sp.sympify(sympy_expr)
            d = sp.diff(parsed, x)
            # численно оценим максимум |d(x)| на сетке
            xs = np.linspace(a, b, n_samples)
            d_lamb = sp.lambdify(x, d, modules=["math", "numpy"])
            vals = np.abs(d_lamb(xs))
            L = float(np.nanmax(vals))
            if L > 0:
                return L
        except Exception:
            pass

    # конечные разности
    xs = np.linspace(a, b, n_samples)
    ys = np.array([f(xi) for xi in xs])
    diffs = np.abs(np.diff(ys)) / np.maximum(np.abs(np.diff(xs)), 1e-16)
    L_est = float(np.nanmax(diffs))
    # Добавим запас (10%) чтобы гарантировать корректность minorant в случае ошибки
    L = max(1e-8, L_est * 1.1)
    # На крайний случай если функция константа
    if L == 0.0:
        L = 1e-6
    return L

class Piyavskiy:
    def __init__(self, f: Callable[[float], float], a: float, b: float, L: float):
        self.f = f
        self.a = a
        self.b = b
        self.L = float(L)
        # Список известных точек (x_i, f_i)
        self.points: List[Tuple[float, float]] = []
        # Начальные точки: концы отрезка
        fa = float(f(a))
        fb = float(f(b))
        self.points = [(a, fa), (b, fb)]
        # Храним minorant (ломаную) аналитически: для каждого отрезка между узлами
        # Но проще генерировать значение minorant p(x) = max_i { f(x_i) - L * |x - x_i| }
        # Для эффективного выбора следующей точки нужно найти минимум p(x) на [a,b].
        # Для p(x) построенной из двух точек (x_i, f_i) пересечения двух линий даёт кандидат.
        self.iterations = 0

    def minorant_value(self, x: float) -> float:
        """Вычислить значение минoранты p(x) = max_i (f_i - L*|x - x_i|)."""
        return max(fi - self.L * abs(x - xi) for xi, fi in self.points)

    def minimizers_candidates(self) -> List[Tuple[float, float]]:
        """
        Для каждой пары точек (xi, fi), (xj, fj) найти точку пересечения прямых
        gi(x) = fi - L*|x - xi| и gj(x) = fj - L*|x - xj|
        (для них на участке между xi,xj это просто fi - L*(x - xi) и fj - L*(xj - x))
        Точка пересечения (если внутри [min(xi,xj), max(xi,xj)]) даёт кандидат для минимума min p(x).
        Также проверяем концы отрезка.
        Возвращает список кандидатов (x_candidate, p(x_candidate)).
        """
        candidates = []
        pts = sorted(self.points, key=lambda t: t[0])
        n = len(pts)
        for i in range(n):
            xi, fi = pts[i]
            # добавить края
            candidates.append((xi, fi - self.L * 0.0))
            # пара с соседями
            if i + 1 < n:
                xj, fj = pts[i + 1]
                # аналитическое пересечение двух прямых, на промежутке [xi, xj] без абсолютов:
                # линия от xi вправо: gi(x) = fi - L*(x - xi)
                # линия от xj влево: gj(x) = fj - L*(xj - x)
                # Решим fi - L*(x - xi) = fj - L*(xj - x)
                # => fi - L*x + L*xi = fj - L*xj + L*x
                # => 2*L*x = fj - fi + L*(xj + xi)
                # => x = (fj - fi) / (2L) + (xj + xi)/2
                denom = 2.0 * self.L
                if denom != 0.0:
                    x_inter = (fj - fi) / denom + (xj + xi) / 2.0
                    if x_inter >= xi - 1e-12 and x_inter <= xj + 1e-12:
                        p_val = max(fi - self.L * abs(x_inter - xi), fj - self.L * abs(x_inter - xj))
                        candidates.append((x_inter, p_val))
        # Гарантируем границы
        candidates.append((self.a, self.minorant_value(self.a)))
        candidates.append((self.b, self.minorant_value(self.b)))
        # Удалим дубликаты по близости x
        uniq = {}
        for x, pv in candidates:
            key = round(float(x), 12)
            if key not in uniq or pv < uniq[key]:
                uniq[key] = pv
        return [(x, uniq[round(x,12)]) for x in sorted(uniq.keys())]

    def next_sample_point(self) -> Tuple[float, float]:
        """
        Находит x*, где p(x) достигает минимума (аппроксимация следующей точки оценки).
        Возвращает (x_star, p(x_star)), без добавления точки в набор (caller добавляет).
        """
        candidates = self.minimizers_candidates()
        # Из кандидатов выбираем мин p_value
        x_star, p_star = min(candidates, key=lambda t: t[1])
        return x_star, p_star

    def run(self, eps: float = 1e-3, max_iter: int = 10000, verbose: bool = False) -> dict:
        """
        Запустить итерационный процесс до достижения условия остановки:
        W(u_n) - p_{n-1}(u_n) < eps
        (т.е. разница между реальным значением функции в выбранной точке и значением минoранты меньше eps)
        Возвращаем словарь с результатами.
        """
        start_time = time.time()
        history = []
        while self.iterations < max_iter:
            x_star, p_star = self.next_sample_point()
            f_x = float(self.f(x_star))
            history.append({
                'iter': self.iterations + 1,
                'x_star': x_star,
                'p_star': p_star,
                'f_x': f_x,
                'gap': f_x - p_star
            })
            # Остановимся, если условие выполнено
            if (f_x - p_star) < eps:
                # Добавим точку и завершили
                self.points.append((x_star, f_x))
                self.iterations += 1
                break
            # Иначе — добавляем точку и продолжаем
            self.points.append((x_star, f_x))
            self.iterations += 1
            if verbose and (self.iterations % 50 == 0):
                print(f"iter {self.iterations}: x={x_star:.6g}, f={f_x:.6g}, gap={f_x - p_star:.6g}")
        total_time = time.time() - start_time

        # Вычислим текущую оценку минимума: берем точку с минимальным значением f среди проб
        xs, fs = zip(*self.points)
        idx_min = int(np.argmin(fs))
        result = {
            'x_min': float(xs[idx_min]),
            'f_min': float(fs[idx_min]),
            'iterations': self.iterations,
            'time': total_time,
            'points': list(self.points),
            'history': history
        }
        return result

    def get_minorant_curve(self, x_grid: np.ndarray) -> np.ndarray:
        """Вычислить значение минoранты на сетке x_grid."""
        return np.array([self.minorant_value(x) for x in x_grid])

def plot_result(f: Callable[[float], float],
                a: float, b: float,
                piy: Piyavskiy,
                result: dict,
                filename: Optional[str] = None,
                show: bool = True):
    """Построить график функции, минoранты и точек."""
    xs = np.linspace(a, b, 2000)
    ys = np.array([f(xi) for xi in xs])
    minor = piy.get_minorant_curve(xs)

    plt.figure(figsize=(10, 6))
    plt.plot(xs, ys, label='f(x)', color='tab:blue')
    plt.plot(xs, minor, label='minorant p(x)', color='tab:green', linestyle='--')
    # точки выборки
    pts_x = [p[0] for p in piy.points]
    pts_y = [p[1] for p in piy.points]
    plt.scatter(pts_x, pts_y, color='red', s=30, zorder=5, label='sample points')
    # Соединить верхние вершины минoранты ломаной (для визуализации)
    # Выберем отсортированные точки и проведём линию g_i = f_i - L*|x - x_i| верхние вершины при каждом x — это minorant,
    # но для наглядности нарисуем ломаную по значениям p(x) в точках xi и в их пересечениях.
    # Найдём пересечения соседних прямых и добавим их
    pts_sorted = sorted(piy.points, key=lambda t: t[0])
    seg_x = []
    seg_y = []
    for i in range(len(pts_sorted)-1):
        xi, fi = pts_sorted[i]
        xj, fj = pts_sorted[i+1]
        # получить точку пересечения как в теории
        denom = 2.0 * piy.L
        if denom != 0:
            x_inter = (fj - fi) / denom + (xj + xi) / 2.0
            if x_inter >= xi and x_inter <= xj:
                seg_x.extend([xi, x_inter])
                seg_y.extend([piy.minorant_value(xi), piy.minorant_value(x_inter)])
            else:
                seg_x.append(xi)
                seg_y.append(piy.minorant_value(xi))
        else:
            seg_x.append(xi)
            seg_y.append(piy.minorant_value(xi))
    # добавить последний
    if pts_sorted:
        seg_x.append(pts_sorted[-1][0])
        seg_y.append(piy.minorant_value(pts_sorted[-1][0]))
    if seg_x:
        plt.plot(seg_x, seg_y, color='green', linewidth=2, alpha=0.6, label='minorant polygon')

    # отметка найденного минимума
    plt.scatter([result['x_min']], [result['f_min']], color='black', s=60, zorder=10, label='found min')
    plt.annotate(f"x*={result['x_min']:.6g}\nf*={result['f_min']:.6g}",
                 xy=(result['x_min'], result['f_min']),
                 xytext=(10, -40), textcoords='offset points',
                 arrowprops=dict(arrowstyle='->', color='black'))

    plt.title(f"Piyavskii method: iterations={result['iterations']}, time={result['time']:.4f}s")
    plt.xlabel('x')
    plt.ylabel('f(x)')
    plt.legend()
    plt.grid(True)
    if filename:
        plt.savefig(filename, dpi=200)
    if show:
        plt.show()
    plt.close()

def rastrigin_1d(x: float, A: float = 10.0) -> float:
    # 1D Rastrigin: A + x^2 - A*cos(2*pi*x)
    return A + x*x - A * math.cos(2.0 * math.pi * x)

def multimodal_example(x: float) -> float:
    # Комбинация синусов и парабол для нескольких локальных минимумов
    return (x**2) + 2.0 * (math.sin(3.0 * x) + 0.5 * math.sin(7.0 * x))

def demo_from_string(expr: str, a: float, b: float, eps: float,
                     use_sympy_estimate: bool = True,
                     max_iter: int = 1000,
                     plotfile: Optional[str] = "piyavskii_result.png"):
    """
    Полный сценарий:
    - Парсим функцию
    - Оцениваем L
    - Запускаем метод
    - Строим визуализацию и выводим результаты
    """
    print("Parsing function...")
    f = make_function_from_string(expr)
    sympy_expr = None
    if _HAS_SYM:
        # Попытаемся взять правую часть выражения (после '=') для sympy
        if '=' in expr:
            sympy_expr = expr.split('=', 1)[1].strip()
        else:
            sympy_expr = expr.strip()

    print("Estimating Lipschitz constant (L)...")
    L = estimate_lipschitz_constant(f, a, b, n_samples=2000, use_sympy=use_sympy_estimate, sympy_expr=sympy_expr)
    print(f"Estimated L = {L:.6g}")

    piy = Piyavskiy(f, a, b, L)
    print("Running Piyavskii method...")
    result = piy.run(eps=eps, max_iter=max_iter, verbose=False)

    print("Done.")
    print(f"Found x* = {result['x_min']:.10g}")
    print(f"Found f* = {result['f_min']:.10g}")
    print(f"Iterations = {result['iterations']}, Time = {result['time']:.6f} s")
    # Plot
    plot_result(f, a, b, piy, result, filename=plotfile, show=True)
    return result


if __name__ == "__main__":
    # Пример 1: Rastrigin 1D на интервале [-5.12, 5.12] (несколько локальных минимумов).
    # expr_rastr = "10 + x**2 - 10*cos(2*pi*x)"
    # print("Demo: 1D Rastrigin function")
    # res1 = demo_from_string(expr_rastr, a=-5.12, b=5.12, eps=1e-3, use_sympy_estimate=_HAS_SYM, max_iter=500, plotfile="rastrigin_piyavskii.png")

    # Пример 2: пользовательская многомодальная функция
    expr_multimodal = "x**2 + 2*(sin(3*x) + 0.5*sin(7*x))"
    print("\nDemo: multimodal example")
    res2 = demo_from_string(expr_multimodal, a=-5.0, b=5.0, eps=1e-3, use_sympy_estimate=_HAS_SYM, max_iter=500, plotfile="multimodal_piyavskii.png")

    # Можно распечатать историю итераций при желании
    print("\nПоследние 10 итераций для Rastrigin:")
    for h in res2['history'][-10:]:
        print(h)