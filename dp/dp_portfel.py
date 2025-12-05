from functools import lru_cache
import math
from typing import List, Tuple, Optional, Dict

Scenario = Tuple[float, float, float, float]   # (p, m1, m2, md)
StateTuple = Tuple[int, int, int, int]         # (n1, n2, nd, cash)
Action = Tuple[int, int, int, int, int, int]   # (new_n1,new_n2,new_nd,cash_after,buy_cost,sell_profit)

class DPOptimizer:
    def __init__(
        self,
        U1: float, U2: float, Ud: float,
        c1: float, c2: float, cd: float,
        stages: List[List[Scenario]],
        initial_state: StateTuple,
        max_n1_limit: int = 120,
        max_n2_limit: int = 40,
        max_nd_limit: int = 80,
        search_radius: Optional[int] = None,
        max_package_changes: Optional[int] = 8,
    ):
        # Конвертация в целые
        self.U1 = int(round(U1 * 100.0))
        self.U2 = int(round(U2 * 100.0))
        self.Ud = int(round(Ud * 100.0))
        # комиссии
        self.c1 = c1
        self.c2 = c2
        self.cd = cd
        # сценарии (p,m1,m2,md)
        self.stages = stages
        self.T = len(stages)
        # начальное состояние (n1,n2,nd,cash)
        self.initial_state = initial_state
        # ограничения на перебор
        self.MAX_N1 = max_n1_limit
        self.MAX_N2 = max_n2_limit
        self.MAX_ND = max_nd_limit
        self.search_radius = search_radius
        # ограничение на суммарные изменения пакетов за один шаг
        self.MAX_PACKAGE_CHANGES = max_package_changes
        self._policy_cache: Dict[Tuple[int,int,int,int,int], Tuple[int, Optional[Action]]] = {}
        self._V = None

    def max_packages_bounds(self, total_wealth_c: int):
        max_n1 = int(total_wealth_c // self.U1) + 1
        max_n2 = int(total_wealth_c // self.U2) + 1
        max_nd = int(total_wealth_c // self.Ud) + 1
        return min(max_n1, self.MAX_N1), min(max_n2, self.MAX_N2), min(max_nd, self.MAX_ND)

    def solve(self) -> Tuple[float, Optional[Action]]:
        @lru_cache(maxsize=None)
        def V(stage_index: int, n1: int, n2: int, nd: int, cash_c: int) -> Tuple[int, Optional[Action]]:
            key = (stage_index, n1, n2, nd, cash_c)
            # Итог:
            if stage_index >= self.T:
                total_c = n1 * self.U1 + n2 * self.U2 + nd * self.Ud + cash_c
                self._policy_cache[key] = (total_c, None)
                return total_c, None

            # Общая текущая сумма
            total = n1 * self.U1 + n2 * self.U2 + nd * self.Ud + cash_c
            max_n1, max_n2, max_nd = self.max_packages_bounds(total)

            # лимиты продажи
            max_sell_n1 = n1
            max_sell_n2 = n2
            max_sell_nd = nd

            # максимальные потенциальные покупки
            max_buy_n1 = max_n1 - n1
            max_buy_n2 = max_n2 - n2
            max_buy_nd = max_nd - nd

            if self.search_radius is None:
                delta1_range = range(-max_sell_n1, max_buy_n1 + 1)
                delta2_range = range(-max_sell_n2, max_buy_n2 + 1)
                delta3_range = range(-max_sell_nd, max_buy_nd + 1)
            else:
                lo1 = max(-max_sell_n1, -self.search_radius)
                hi1 = min(max_buy_n1, self.search_radius)
                lo2 = max(-max_sell_n2, -self.search_radius)
                hi2 = min(max_buy_n2, self.search_radius)
                lo3 = max(-max_sell_nd, -self.search_radius)
                hi3 = min(max_buy_nd, self.search_radius)
                delta1_range = range(lo1, hi1 + 1)
                delta2_range = range(lo2, hi2 + 1)
                delta3_range = range(lo3, hi3 + 1)

            best_EV = -10**30
            best_action = None

            use_pkg_limit = (self.MAX_PACKAGE_CHANGES is not None)

            for d1 in delta1_range:
                new_n1 = n1 + d1
                if new_n1 < 0 or new_n1 > self.MAX_N1:
                    continue

                for d2 in delta2_range:
                    new_n2 = n2 + d2
                    if new_n2 < 0 or new_n2 > self.MAX_N2:
                        continue

                    if use_pkg_limit and (abs(d1) + abs(d2) > self.MAX_PACKAGE_CHANGES):
                        continue

                    for d3 in delta3_range:
                        if use_pkg_limit and (abs(d1) + abs(d2) + abs(d3) > self.MAX_PACKAGE_CHANGES):
                            continue

                        new_nd = nd + d3
                        if new_nd < 0 or new_nd > self.MAX_ND:
                            continue

                        # вычисляем стоимость покупок и выручку от продаж
                        buy_cost = 0
                        sell_profit = 0

                        if d1 > 0:
                            buy_cost += int(round(d1 * self.U1 * (1.0 + self.c1)))
                        elif d1 < 0:
                            sell_profit += int(round((-d1) * self.U1 * (1.0 - self.c1)))

                        if d2 > 0:
                            buy_cost += int(round(d2 * self.U2 * (1.0 + self.c2)))
                        elif d2 < 0:
                            sell_profit += int(round((-d2) * self.U2 * (1.0 - self.c2)))

                        if d3 > 0:
                            buy_cost += int(round(d3 * self.Ud * (1.0 + self.cd)))
                        elif d3 < 0:
                            sell_profit += int(round((-d3) * self.Ud * (1.0 - self.cd)))

                        cash_after = cash_c - buy_cost + sell_profit
                        if cash_after < 0:
                            continue

                        EV_acc = 0.0
                        for scen in self.stages[stage_index]:
                            p, m1, m2, md = scen
                            h1 = (new_n1 * self.U1) * m1
                            h2 = (new_n2 * self.U2) * m2
                            hd = (new_nd * self.Ud) * md

                            next_n1 = int(math.floor(h1 / float(self.U1) + 1e-9))
                            next_n2 = int(math.floor(h2 / float(self.U2) + 1e-9))
                            next_nd = int(math.floor(hd / float(self.Ud) + 1e-9))

                            rem1 = int(round(h1 - next_n1 * self.U1))
                            rem2 = int(round(h2 - next_n2 * self.U2))
                            remd = int(round(hd - next_nd * self.Ud))

                            next_cash = cash_after + rem1 + rem2 + remd

                            val_next, _ = V(stage_index + 1, next_n1, next_n2, next_nd, next_cash)
                            EV_acc += p * float(val_next)

                        EV_int = int(round(EV_acc))
                        if EV_int > best_EV:
                            best_EV = EV_int
                            best_action = (new_n1, new_n2, new_nd, cash_after, buy_cost, sell_profit)

            if best_action is None:
                total_c = n1 * self.U1 + n2 * self.U2 + nd * self.Ud + cash_c
                self._policy_cache[key] = (total_c, None)
                return total_c, None

            self._policy_cache[key] = (best_EV, best_action)
            return best_EV, best_action

        # Запоминаем функцию
        self._policy_cache.clear()
        self._V = V
        n1_0, n2_0, nd_0, cash0 = self.initial_state
        ev_c, action = V(0, n1_0, n2_0, nd_0, cash0)
        return ev_c / 100.0, action

    def get_policy_cache(self):
        return self._policy_cache

    def format_money(self, cents: int) -> str:
        return f"{cents/100.0:.2f} д.е."

    def print_policy_tree(self, max_depth: Optional[int] = None):
        if not self._policy_cache or self._V is None:
            raise RuntimeError("Сначала вызовите solve(), чтобы заполнить policy cache.")

        def recurse(stage_index: int, n1: int, n2: int, nd: int, cash_c: int, indent: str = ""):
            key = (stage_index, n1, n2, nd, cash_c)
            if key in self._policy_cache:
                ev_c, act = self._policy_cache[key]
                print(f"{indent}Этап {stage_index}: состояние: CB1={n1}, CB2={n2}, Dep={nd}, cash={self.format_money(cash_c)}; EV = {self.format_money(ev_c)}")
            else:
                print(f"{indent}Этап {stage_index}: состояние: CB1={n1}, CB2={n2}, Dep={nd}, cash={self.format_money(cash_c)}")
                # если состояние не посещалось — нечего рекомендовать
                return

            if stage_index >= self.T:
                print(f"{indent}  -> Конец ветки. Итоговая стоимость - {self.format_money(n1 * self.U1 + n2 * self.U2 + nd * self.Ud + cash_c)}")
                return

            ev_c, act = self._policy_cache.get(key, (None, None))
            if act is None:
                print(f"{indent}  -> Рекомендация: ничего не менять.")
                # переход к следующему этапу без изменений
                if stage_index+1 <= self.T:
                    recurse(stage_index+1, n1, n2, nd, cash_c, indent + "    ")
                return

            new_n1, new_n2, new_nd, cash_after, buy_cost, sell_profit = act
            # вывод действие
            print(f"{indent}  -> Рекомендация перед этапом {stage_index+1}: держать CB1={new_n1}, CB2={new_n2}, Dep={new_nd}; cash после операции={self.format_money(cash_after)}; buy_cost={self.format_money(buy_cost)}, sell_profit={self.format_money(sell_profit)}")

            # применяем действие
            for i, scen in enumerate(self.stages[stage_index]):
                p, m1, m2, md = scen
                # вычисляем новую стоимость пакетов
                h1_post = (new_n1 * self.U1) * m1
                h2_post = (new_n2 * self.U2) * m2
                hd_post = (new_nd * self.Ud) * md

                next_n1 = int(math.floor(h1_post / float(self.U1) + 1e-9))
                next_n2 = int(math.floor(h2_post / float(self.U2) + 1e-9))
                next_nd = int(math.floor(hd_post / float(self.Ud) + 1e-9))

                rem1 = int(round(h1_post - next_n1 * self.U1))
                rem2 = int(round(h2_post - next_n2 * self.U2))
                remd = int(round(hd_post - next_nd * self.Ud))

                next_cash = cash_after + rem1 + rem2 + remd

                print(f"{indent}    Сценарий {stage_index+1}.{i+1} (p={p:.2f}): коэффициенты (m1={m1}, m2={m2}, md={md}) -> перед этапом {stage_index+1+1} состояние: CB1={next_n1}, CB2={next_n2}, Dep={next_nd}, cash={self.format_money(next_cash)}")
                # глубина - ограничение
                if (max_depth is not None) and (stage_index+1 >= max_depth):
                    continue
                recurse(stage_index+1, next_n1, next_n2, next_nd, next_cash, indent + "      ")

        # начальное состояние
        n1_0, n2_0, nd_0, cash0 = self.initial_state
        recurse(0, n1_0, n2_0, nd_0, cash0, "")


if __name__ == "__main__":
    # стоимость одного пакетов
    U1 = 25.0; U2 = 200.0; Ud = 100.0
    # комиссии
    c1 = 0.04; c2 = 0.07; cd = 0.05

    # сценарии (p,m1,m2,md)
    stages = [
        [(0.60,1.20,1.10,1.07),(0.30,1.05,1.02,1.03),(0.10,0.80,0.95,1.00)],
        [(0.30,1.40,1.15,1.01),(0.50,1.05,1.01,1.00),(0.20,0.60,0.90,1.00)],
        [(0.40,1.15,1.12,1.05),(0.40,1.05,1.01,1.01),(0.20,0.70,0.94,1.00)]
    ]

    # Начальное состояние: числа пакетов и cash
    n1_0 = 100 // 25
    n2_0 = 800 // 200
    nd_0 = 400 // 100
    cash0 = int(round(600.0 * 100.0))

    initial_state = (n1_0, n2_0, nd_0, cash0)

    opt = DPOptimizer(
        U1=U1, U2=U2, Ud=Ud,
        c1=c1, c2=c2, cd=cd,
        stages=stages,
        initial_state=initial_state,
        search_radius=4,           # радиус перебора
        max_package_changes=8,     # ограничение пакетов изменений за шаг
    )

    ev, action = opt.solve()
    print(f"EV = {ev:.2f} д.е.")
    print("action (initial):", action)
    print("\nДерево рекомендаций:")
    opt.print_policy_tree()