import numpy as np

import numpy as np

def find_start_basis(A):
    m, n = A.shape
    basis = [None] * m
    for j in range(n):
        col = A[:, j]
        if np.count_nonzero(col) == 1 and (col == 1).any():
            row_idx = np.where(col == 1)[0][0]
            if basis[row_idx] is None:
                basis[row_idx] = j

    # Проверим, что базис найден полностью:
    if any(x is None for x in basis):
        raise ValueError("Не удалось найти полный базис. Проверьте матрицу ограничений!")
    return basis

def build_simplex_tableau(A, b, c, var_types, base_var_types):
    """
    A - матрица ограничений (m x n)
    b - правая часть (m,)
    c - коэффициенты целевой функции (n,)
    var_types - типы переменных (например, '+', 'slack', 'artificial', ...)
    base_var_types - типы базисных переменных по строкам
    Возвращает: симплекс-таблицу (m+1 x n+1)
    """
    m, n = A.shape
    tableau = np.zeros((m + 1, n + 1))
    tableau[:m, :n] = A
    tableau[:m, n] = b
    tableau[m, :n] = c
    tableau[m, n] = 0
    return tableau


# Для обработки искусственных переменных:
def find_artificial_indices(var_types):
    """Возвращает список индексов искусственных переменных"""
    return [i for i, vtype in enumerate(var_types) if vtype == "artificial"]


def build_auxiliary_objective(var_types, n):
    """Строит коэффициенты вспомогательной целевой функции (для первой фазы)"""
    aux_c = np.zeros(n)
    for i, vtype in enumerate(var_types):
        if vtype == "artificial":
            aux_c[i] = 1  # Суммируем искусственные переменные
    return aux_c


if __name__ == "__main__":
    A = np.array([
        [1, 0, 0, 1, 0, 0],
        [0, 1, -1, 0, 1, 0],
        [1, 1, 1, 0, 0, 1]
    ])
    b = np.array([4, 2, 5])
    c = np.array([2, 3, -1, 0, 0, 0])
    var_types = ['+', '+', '+', 'slack', 'slack', 'artificial']
    base_var_types = ['slack', 'slack', 'artificial']

    tableau = build_simplex_tableau(A, b, c, var_types, base_var_types)
    print("Симплекс-таблица:\n", tableau)

    # Если есть artificial-переменные:
    artificial_inds = find_artificial_indices(var_types)
    if artificial_inds:
        aux_c = build_auxiliary_objective(var_types, A.shape[1])
        print("Вспомогательная целевая функция:", aux_c)
        aux_tableau = build_simplex_tableau(A, b, aux_c, var_types, base_var_types)
        print("Вспомогательная симплекс-таблица:\n", aux_tableau)