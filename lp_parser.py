import numpy as np

def read_lp_file(filename):
    """
    Читает задачу линейного программирования из текстового файла:
    Возвращает:
      - цель ('min' или 'max')
      - массив коэффициентов целевой функции
      - список ограничений (каждое ограничение — кортеж (коэффициенты, знак, правая часть))
      - список типов переменных: '+' (неотрицательная), 'free' (свободная)
    """
    with open(filename, 'r') as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    # Первая строка — целевая функция
    parts = lines[0].split()
    objective = parts[0].lower()  # min или max
    c = np.array([float(x) for x in parts[1:]])

    # По умолчанию все переменные неотрицательные
    var_types = ['+'] * len(c)

    # Проверяем строку vars
    constraints_start = 1
    if lines[1].startswith('vars:'):
        var_types = []
        var_line = lines[1][5:].strip()
        for v in var_line.split():
            if v == '+':
                var_types.append('+')
            elif v.lower() == 'free':
                var_types.append('free')
            else:
                raise ValueError(f"Неизвестный тип переменной: {v}")
        constraints_start = 2  # ограничения начинаются со следующей строки

    # Остальные строки — ограничения
    constraints = []
    for line in lines[constraints_start:]:
        tokens = line.split()
        sign = tokens[-2]
        b = float(tokens[-1])
        a = np.array([float(x) for x in tokens[:-2]])
        constraints.append((a, sign, b))

    return objective, c, constraints, var_types

# Пример использования:
if __name__ == "__main__":
    objective, c, constraints, var_types = read_lp_file("lp.txt")
    print("Цель:", objective)
    print("Коэффициенты целевой функции:", c)
    print("Типы переменных:", var_types)
    print("Ограничения:")
    for a, sign, b in constraints:
        print(f"  {a} {sign} {b}")