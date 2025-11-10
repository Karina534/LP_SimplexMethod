import numpy as np

def find_pivot_column(tableau):
    """
    Функция для поиска столбца с самым выгодным для улучшения коэффициента
    :param tableau: симплекс-таблица
    :return: Индекс опорного столбца или None, если нет отрицательных значений
    """
    last_row = tableau[-1, :-1]  # Строка коэффициентов целевой функции
    min_val = np.min(last_row)
    if min_val >= -1e-10:  # допускаем маленькие ошибки округления
        return None
    return np.argmin(last_row)

def find_pivot_row(tableau, pivot_col):
    """
    Функция для поиска разрешающей строки.
    :param tableau: Симплекс-таблица
    :param pivot_col: Разрешающий столбец
    :return: Индекс строки с минимальным положительным отношением
    """
    column = tableau[:-1, pivot_col]  # Берём столбец по pivot_col
    rhs = tableau[:-1, -1]  # Свободные члены (правая часть) ограничений
    ratios = []  # Массив отношений, чтобы выбрать наиболее существенный опорный элемент
    for i in range(len(column)):
        if column[i] > 1e-12:  # Только если элемент положителен (>0)
            ratios.append(rhs[i] / column[i])  # Вычисляем отношение
        else:
            ratios.append(np.inf)  # Если элемент <=0, отношение не считаем (ставим бесконечность)
    if all(r == np.inf for r in ratios):  # Если ни для одного ограничения нельзя выбрать строку
        return None  # Неограниченность задачи
    return np.argmin(ratios)

def pivot(tableau, pivot_row, pivot_col):
    new_tableau = tableau.copy()
    pr = pivot_row
    pc = pivot_col
    pivot_elem = tableau[pr, pc]  # Опорный элемент
    new_tableau[pr, :] = tableau[pr, :] / pivot_elem  # Делим разрешающую строку на разрешающий элемент
    for i in range(tableau.shape[0]):
        if i != pr:
            # Обнуляем все остальные элементы в опорном столбце
            new_tableau[i, :] = tableau[i, :] - tableau[i, pc] * new_tableau[pr, :]
    return new_tableau

def simplex_phase(tableau, basis, var_types, artificial_inds=None, tol=1e-8):
    m, n = tableau.shape
    m -= 1
    n -= 1
    while True:
        pivot_col = find_pivot_column(tableau)  # Опорный столбец
        if pivot_col is None:
            # Оптимум найден
            # Если это вспомогательная задача, проверяем artificial
            if artificial_inds is not None:
                Q = tableau[-1, -1]
                # Если вспомогательная цель > 0 => несовместна
                if abs(Q) > tol:
                    return tableau, basis, False
                # Иначе — Q == 0: убедимся, что никакая artificial базисная переменная не имеет положительного RHS
                # Если искусственная переменная в базисе, её значение = RHS соответствующей строки
                for art in artificial_inds:
                    if art in basis:
                        row_idx = basis.index(art)
                        if abs(tableau[row_idx, -1]) > tol:
                            return tableau, basis, False
                # Допускаем фазу 2
            return tableau, basis, True

        pivot_row = find_pivot_row(tableau, pivot_col)
        print("pivot_col = ", pivot_col, "pivot_row = ", pivot_row)
        if pivot_row is None:
            print("Задача неограниченна.")
            return tableau, basis, False
        basis[pivot_row] = pivot_col  # Обновление базиса
        tableau = pivot(tableau, pivot_row, pivot_col)
        print("After iteration:\n", tableau)
