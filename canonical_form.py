import numpy as np

from lp_parser import read_lp_file


def to_canonical(objective, c, constraints, var_types):
    """
    Приводит задачу ЛП к каноническому виду.
    Добавляет slack, surplus и artificial переменные там, где нужно,
    чтобы обеспечить наличие базиса (единичных столбцов).
    Возвращает (c_canon, A, b, var_names, var_types_out, mapping).
    """
    n = len(c)
    m = len(constraints)

    # Начальные имена и типы переменных (исходные)
    var_names = [f'x{i+1}' for i in range(n)]
    var_types_out = var_types[:]  # копия

    # Начальная матрица A (заполним исходными коэффициентами)
    A = np.zeros((m, n))
    b = np.zeros(m)

    for i, (a_row, sign, bi) in enumerate(constraints):
        A[i, :len(a_row)] = a_row
        b[i] = bi

    # Добавляем дополнительные столбцы по каждому ограничению
    artificial_count = 0
    for i, (_, sign, _) in enumerate(constraints):
        if sign == "<=":
            # добавляем slack (1 в строке i)
            col = np.zeros(m)
            col[i] = 1.0
            A = np.hstack([A, col.reshape(m, 1)])
            var_names.append(f's{i+1}')
            var_types_out.append('slack')
        elif sign == ">=":
            # добавляем surplus (-1 в строке i)
            col_surplus = np.zeros(m)
            col_surplus[i] = -1.0
            A = np.hstack([A, col_surplus.reshape(m, 1)])
            var_names.append(f's{i+1}')
            var_types_out.append('surplus')
            # и искусственную переменную (1 в строке i) для базиса
            col_art = np.zeros(m)
            col_art[i] = 1.0
            A = np.hstack([A, col_art.reshape(m, 1)])
            artificial_count += 1
            var_names.append(f'a{artificial_count}')
            var_types_out.append('artificial')
        elif sign == "=":
            # прямая запись: добавляем искусственную переменную (1 в строке i)
            col_art = np.zeros(m)
            col_art[i] = 1.0
            A = np.hstack([A, col_art.reshape(m, 1)])
            artificial_count += 1
            var_names.append(f'a{artificial_count}')
            var_types_out.append('artificial')
        else:
            raise ValueError(f"Неизвестный знак ограничения: {sign}")

    # Привести целевую функцию к минимуму
    added_cols = A.shape[1] - n
    c_canon = np.concatenate([c, np.zeros(added_cols)])
    if objective == 'max':
        c_canon = -c_canon

    # Простое соответствие исходных переменных (по столбцам)
    mapping = [[i] for i in range(n)]

    return c_canon, A, b, var_names, var_types_out, mapping

# Пример использования:
if __name__ == "__main__":
    # min -2 -3 1 -1 0 0
    # 1 0 0 1 0 0 = 7
    # 2 0 6 0 1 0 = 5
    # 0 1 -1 0 0 1 = 2

    # objective = "min"
    # c = np.array([-2, -3, 1, -1, 0, 0])
    # var_types = ['+'] * 6
    # constraints = [
    #     (np.array([1, 0, 0, 1, 0, 0]), "=", 7),
    #     (np.array([2, 0, 6, 0, 1, 0]), "=", 5),
    #     (np.array([0, 1, -1, 0, 0, 1]), "=", 2)
    # ]

    objective, c, constraints, var_types = read_lp_file("lp.txt")
    c_canon, A, b, var_names, var_types_out, mapping = to_canonical(objective, c, constraints, var_types)
    print("Коэффициенты цели (канонический вид):", c_canon)
    print("Матрица ограничений:\n", A)
    print("Правая часть:", b)
    print("Все переменные:", var_names)
    print("Типы переменных:", var_types_out)
    print("mapping:", mapping)