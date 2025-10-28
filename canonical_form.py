import numpy as np

def expand_variables(c, var_types, constraints):
    """
    Разворачивает free-переменные:
    x_j = x_j_plus - x_j_minus, где обе >= 0.
    Возвращает: new_c, new_constraints, new_var_types, var_names, mapping
    mapping[j] = список индексов в расширённой системе, соответствующих исходной переменной j
    """
    new_c = []
    new_var_types = []
    var_names = []
    mapping = []

    # Раскладываем целевую функцию и имена переменных
    for i, vtype in enumerate(var_types):
        if vtype == '+':
            new_c.append(c[i])
            new_var_types.append('+')
            var_names.append(f'x{i+1}')
            mapping.append([len(new_c)-1])
        elif vtype == 'free':
            # x = x_plus - x_minus
            new_c.append(c[i])      # для x_plus
            new_c.append(-c[i])     # для x_minus
            new_var_types.extend(['+', '+'])
            var_names.extend([f'x{i+1}_plus', f'x{i+1}_minus'])
            mapping.append([len(new_c)-2, len(new_c)-1])
        else:
            raise ValueError(f"Неизвестный тип переменной: {vtype}")

    new_c = np.array(new_c, dtype=float)

    # Расширяем коэффициенты ограничений
    new_constraints = []
    for a_row, sign, bi in constraints:
        new_row = []
        for i, vtype in enumerate(var_types):
            if vtype == '+':
                new_row.append(a_row[i])
            elif vtype == 'free':
                new_row.append(a_row[i])    # coef для x_plus
                new_row.append(-a_row[i])   # coef для x_minus
        new_constraints.append((np.array(new_row, dtype=float), sign, bi))

    return new_c, new_constraints, new_var_types, var_names, mapping

def to_canonical(objective, c, constraints, var_types):
    """
    Приводит задачу ЛП к каноническому виду.
    Сначала разворачивает free-переменные через expand_variables,
    затем добавляет slack/surplus/artificial. Возвращает:
    c_canon, A, b, var_names, var_types_out, mapping
    """
    # 1) Разворачиваем free-переменные (если есть)
    c_exp, constraints_exp, var_types_exp, var_names_exp, mapping = expand_variables(c, var_types, constraints)

    n = len(c_exp)            # число переменных после разворачивания free
    m = len(constraints_exp)

    # Инициализация A и b по расширённым данным
    var_names = var_names_exp[:]       # имена исходных/развернутых переменных
    var_types_out = var_types_exp[:]   # текущие типы (обычно '+')

    A = np.zeros((m, n))
    b = np.zeros(m)
    for i, (a_row, sign, bi) in enumerate(constraints_exp):
        if len(a_row) != n:
            row = np.zeros(n)
            row[:len(a_row)] = a_row
            A[i, :] = row
        else:
            A[i, :] = a_row
        b[i] = bi

    # 2) Добавляем дополнительные столбцы (slack/surplus/artificial)
    artificial_count = 0
    for i, (_, sign, _) in enumerate(constraints_exp):
        if sign == "<=":
            col = np.zeros(m); col[i] = 1.0
            A = np.hstack([A, col.reshape(m,1)])
            var_names.append(f's{i+1}')
            var_types_out.append('slack')
        elif sign == ">=":
            col_sur = np.zeros(m); col_sur[i] = -1.0
            A = np.hstack([A, col_sur.reshape(m,1)])
            var_names.append(f's{i+1}')
            var_types_out.append('surplus')
            col_art = np.zeros(m); col_art[i] = 1.0
            A = np.hstack([A, col_art.reshape(m,1)])
            artificial_count += 1
            var_names.append(f'a{artificial_count}')
            var_types_out.append('artificial')
        elif sign == "=":
            col_art = np.zeros(m); col_art[i] = 1.0
            A = np.hstack([A, col_art.reshape(m,1)])
            artificial_count += 1
            var_names.append(f'a{artificial_count}')
            var_types_out.append('artificial')
        else:
            raise ValueError(f"Неизвестный знак ограничения: {sign}")

    # 3) Подготовка коэффициентов целевой функции (к минимуму)
    added_cols = A.shape[1] - n
    c_canon = np.concatenate([c_exp, np.zeros(added_cols)])
    if objective == 'max':
        c_canon = -c_canon

    return c_canon, A, b, var_names, var_types_out, mapping

def recover_original_variables(x_extended, mapping):
    """Восстанавливает вектор исходных переменных по расширённому решению и mapping."""
    x_orig = []
    for inds in mapping:
        if len(inds) == 1:
            x_orig.append(x_extended[inds[0]])
        elif len(inds) == 2:
            x_orig.append(x_extended[inds[0]] - x_extended[inds[1]])
        else:
            raise ValueError("Unexpected mapping length")
    return np.array(x_orig)