import numpy as np

from simplex_method.lp_parser import read_lp_file
from simplex_method.canonical_form import to_canonical
from simplex_method.simplex_phase import simplex_phase
from simplex_method.simplex_table import find_artificial_indices, build_auxiliary_objective, build_simplex_tableau, find_start_basis

def remap_basis_after_deletion(old_basis, deleted_inds):
    """
    Возвращает новый список базисных индексов после удаления столбцов deleted_inds из матрицы.
    deleted_inds может быть неотсортированным; здесь работаем с отсортированным.
    """
    deleted_sorted = sorted(deleted_inds)
    new_basis = []
    for bi in old_basis:
        if bi in deleted_sorted:
            # этот базисный столбец удалён — не включаем его
            continue
        # число удалённых столбцов слева от bi
        cnt = sum(1 for d in deleted_sorted if d < bi)
        new_basis.append(bi - cnt)
    return new_basis

def two_phase_simplex(objective, c, constraints, var_types, verbose=True):
    c_ext, A, b, var_names, var_types_out, mapping = to_canonical(objective, c, constraints, var_types)
    m, n = A.shape

    artificial_inds = find_artificial_indices(var_types_out)
    if verbose:
        print("artificial_inds: ", artificial_inds)
        print("var_names: ", var_names)
        print("var_types_out", var_types_out)

    basis = find_start_basis(A)
    if verbose:
        print("basis:", basis)
        print("Базисные переменные и их типы:")
        for i, bi in enumerate(basis):
            print(f"Строка {i}: переменная {bi} ({var_types_out[bi]})")

    if artificial_inds:
        aux_c = build_auxiliary_objective(var_types_out, A.shape[1])
        for i in artificial_inds:
            aux_c[i] = 1.0
        tableau = build_simplex_tableau(A, b, aux_c, var_types_out, var_types)

        # Корректировка строки цели (считаем последнюю строку как c_B * B^{-1} * A - c для искусственной функции)
        for i, bi in enumerate(basis):
            if var_types_out[bi] == 'artificial':
                tableau[-1, :] -= tableau[i, :]

        if verbose:
            print("Стартовая симплекс-таблица для вспомогательной задачи:")
            print(tableau)
        tableau, basis, ok = simplex_phase(tableau, basis, var_types_out, artificial_inds)
        if not ok:
            print("Система несовместна: допустимых решений нет.")
            return None, None, None

        # Удаляем столбцы искусственных переменных из tableau и из A, c_ext, var_names, var_types_out
        # Сначала сортируем индексы для удаление
        deleted = sorted(artificial_inds)
        # Удаляем одновременно из tableau (по столбцам), и из A и c_ext и списков имён/типов
        tableau = np.delete(tableau, deleted, axis=1)
        A = np.delete(A, deleted, axis=1)
        c_ext = np.delete(c_ext, deleted)
        var_names = [v for i, v in enumerate(var_names) if i not in deleted]
        var_types_out = [v for i, v in enumerate(var_types_out) if i not in deleted]

        # Пересчитаем базис (индексы столбцов смещаются после удаления)
        basis = remap_basis_after_deletion(basis, deleted)

        if verbose:
            print("Фаза 1 завершена. Искусственные переменные удалены.")
            print("Текущая таблица:\n", tableau)
    else:
        tableau = build_simplex_tableau(A, b, c_ext, var_types_out, var_types)
        if verbose:
            print("Стартовая симплекс-таблица для исходной задачи (без искусственных переменных):")
            print(tableau)

    # Фаза 2
    n = tableau.shape[1] - 1
    tableau[-1, :n] = c_ext
    tableau[-1, -1] = 0
    for i, bi in enumerate(basis):
        tableau[-1, :] -= tableau[-1, bi] * tableau[i, :]

    if verbose:
        print("Начало фазы 2 (основная задача):")
        print(tableau)
    tableau, basis, ok = simplex_phase(tableau, basis, var_types_out)
    if not ok:
        print("Задача неограниченна!")
        return None, None, None

    x = np.zeros(len(var_names))
    for i, bi in enumerate(basis):
        if bi < len(var_names):
            x[bi] = tableau[i, -1]

    return tableau[-1, -1], x, var_names

if __name__ == "__main__":
    objective, c, constraints, var_types = read_lp_file("lp.txt")
    opt_val, x, var_names = two_phase_simplex(objective, c, constraints, var_types, verbose=True)
    if opt_val is not None:
        print("Оптимальное значение:", opt_val)
        for name, xi in zip(var_names, x):
            print(f"{name} = {xi}")
    else:
        print("Решения нет.")