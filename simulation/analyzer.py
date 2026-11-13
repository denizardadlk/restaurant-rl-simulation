from typing import Dict, Any, List, Optional
import numpy as np
from .engine import SimulationEngine

class BottleneckAnalyzer:
    """
    Deep diagnostic bottleneck analyzer for restaurant simulation.
    Tracks station saturation, stage queue delays, starvation vs saturation,
    dish-level churn attribution, and generates prescriptive layout recommendations.
    """
    def __init__(self, engine: SimulationEngine):
        self.engine = engine
        self.engine.analyzer = self
        self.total_ticks_observed = 0

        # 1. Station Metrics
        self.station_busy_ticks: Dict[str, int] = {s_id: 0 for s_id in self.engine.grid.stations}
        self.station_full_ticks: Dict[str, int] = {s_id: 0 for s_id in self.engine.grid.stations}
        self.station_orders_count: Dict[str, int] = {s_id: 0 for s_id in self.engine.grid.stations}

        # 2. Station Type Queue & Blockage Tracking
        station_types = set(s.type for s in self.engine.grid.stations.values())
        station_types.update(["PREP", "OVEN", "GRILL", "STOVE", "FRYER", "TOASTER", "DONER"])
        self.station_type_queue_waits: Dict[str, List[float]] = {st: [] for st in station_types}
        self.station_type_blocked_ticks: Dict[str, int] = {st: 0 for st in station_types}
        self.station_type_total_demands: Dict[str, int] = {st: 0 for st in station_types}

        # 3. Starvation vs Saturation (Chef shortage vs Station capacity shortage)
        self.station_type_saturation_ticks: Dict[str, int] = {st: 0 for st in station_types}
        self.station_type_starvation_ticks: Dict[str, int] = {st: 0 for st in station_types}

        # 4. Chef Metrics
        self.chef_busy_ticks: Dict[str, int] = {c_id: 0 for c_id in self.engine.grid.chefs}
        self.chef_walking_ticks: Dict[str, int] = {c_id: 0 for c_id in self.engine.grid.chefs}
        self.chef_idle_ticks: Dict[str, int] = {c_id: 0 for c_id in self.engine.grid.chefs}

        # 5. Waiter Metrics
        self.waiter_deliver_ticks: Dict[str, int] = {w_id: 0 for w_id in self.engine.grid.waiters}
        self.waiter_order_ticks: Dict[str, int] = {w_id: 0 for w_id in self.engine.grid.waiters}
        self.waiter_clean_ticks: Dict[str, int] = {w_id: 0 for w_id in self.engine.grid.waiters}
        self.waiter_idle_ticks: Dict[str, int] = {w_id: 0 for w_id in self.engine.grid.waiters}

        # 6. Counter Metrics
        all_counters = list(self.engine.grid.delivery_counters.keys())
        if getattr(self.engine.grid, "takeout_counter", None):
            all_counters.append(self.engine.grid.takeout_counter.id)
        if getattr(self.engine.grid, "beverage_counter", None):
            all_counters.append(self.engine.grid.beverage_counter.id)
        self.counter_full_ticks: Dict[str, int] = {c_id: 0 for c_id in all_counters}
        self.counter_total_dishes: Dict[str, int] = {c_id: 0 for c_id in all_counters}

        # 7. Churn Root Causes & Dish Attribution
        self.churn_reasons = {
            "WAITING_ORDER": 0,
            "WAITING_FOOD": 0,
            "TAKEOUT_COURIER": 0
        }
        self.churn_by_dish: Dict[str, int] = {}
        self.churn_by_stage: Dict[str, int] = {st: 0 for st in station_types}

        # 8. Detailed Dish-Level Performance Metrics (ADR-034 aligned)
        self.dish_demands: Dict[str, int] = {}
        self.dish_completions: Dict[str, int] = {}
        self.dish_churns: Dict[str, int] = {}
        self.dish_wait_times: Dict[str, List[float]] = {}
        self.dish_cook_times: Dict[str, List[float]] = {}
        self.dish_cold_times: Dict[str, List[float]] = {}
        self.dish_categories: Dict[str, str] = {}

        # 9. Detailed Staff Operational Task Counters
        self.chef_dish_counts: Dict[str, int] = {c_id: 0 for c_id in self.engine.grid.chefs}
        self.chef_stage_transfers: Dict[str, int] = {c_id: 0 for c_id in self.engine.grid.chefs}
        self.waiter_delivered_dishes: Dict[str, int] = {w_id: 0 for w_id in self.engine.grid.waiters}
        self.waiter_drink_transfers: Dict[str, int] = {w_id: 0 for w_id in self.engine.grid.waiters}
        self.waiter_cleaned_tables: Dict[str, int] = {w_id: 0 for w_id in self.engine.grid.waiters}
        self.waiter_orders_taken: Dict[str, int] = {w_id: 0 for w_id in self.engine.grid.waiters}

        # 10. Hourly / Interval Tracking
        self.interval_metrics: List[Dict[str, Any]] = []
        self._init_interval_trackers()

        # Internal tracking for stage entry times & processed orders
        self._order_stage_entry: Dict[str, float] = {}
        self._seen_orders = set()
        self._processed_completed_ids = set()

    def _init_interval_trackers(self):
        intervals = self.engine.generator.time_config.arrival_schedule.get("intervals", [])
        self.interval_metrics = []
        for itv in intervals:
            self.interval_metrics.append({
                "start_tick": itv["start_tick"],
                "end_tick": itv["end_tick"],
                "description": itv.get("description", f"{itv['start_tick']}-{itv['end_tick']}"),
                "target_occupancy": itv.get("target_occupancy", 0.0),
                "completed_foods": 0,
                "completed_drinks": 0,
                "churn_count": 0,
                "wait_times": []
            })

    def track_tick(self):
        """Called at every simulation tick to collect system state snapshots."""
        self.total_ticks_observed += 1
        tick = self.engine.tick
        day_tick = tick % 1440

        # Register newly created orders in demands & categories
        for o in list(self.engine.order_queue) + list(self.engine.completed_orders):
            if o.order_id not in self._seen_orders:
                self._seen_orders.add(o.order_id)
                d_type = o.dish_type
                cat = getattr(o, "category", "main_dish")
                self.dish_demands[d_type] = self.dish_demands.get(d_type, 0) + 1
                self.dish_categories[d_type] = cat
                if d_type not in self.dish_completions:
                    self.dish_completions[d_type] = 0
                if d_type not in self.dish_churns:
                    self.dish_churns[d_type] = 0
                if d_type not in self.dish_wait_times:
                    self.dish_wait_times[d_type] = []
                if d_type not in self.dish_cook_times:
                    self.dish_cook_times[d_type] = []
                if d_type not in self.dish_cold_times:
                    self.dish_cold_times[d_type] = []

        # Track completed orders metrics (Wait time, Cook time, Cold time)
        for o in self.engine.completed_orders:
            if o.order_id not in self._processed_completed_ids:
                self._processed_completed_ids.add(o.order_id)
                d_type = o.dish_type
                self.dish_completions[d_type] = self.dish_completions.get(d_type, 0) + 1
                
                # Wait time in queue
                if o.timestamps.get("kitchen_start") and o.timestamps.get("created_at"):
                    q_wait = float(o.timestamps["kitchen_start"] - o.timestamps["created_at"])
                    self.dish_wait_times[d_type].append(q_wait)
                    # Add to current interval
                    for itv in self.interval_metrics:
                        if itv["start_tick"] <= day_tick < itv["end_tick"]:
                            itv["wait_times"].append(q_wait)
                            break

                # Cook time
                if o.timestamps.get("kitchen_finish") and o.timestamps.get("kitchen_start"):
                    c_time = float(o.timestamps["kitchen_finish"] - o.timestamps["kitchen_start"])
                    self.dish_cook_times[d_type].append(c_time)

                # Cold time
                if o.timestamps.get("delivered_at") and o.timestamps.get("kitchen_finish"):
                    cold_time = max(0.0, float(o.timestamps["delivered_at"] - o.timestamps["kitchen_finish"] - 5.0))
                    self.dish_cold_times[d_type].append(cold_time)

                # Interval completed counters
                cat = getattr(o, "category", "main_dish")
                for itv in self.interval_metrics:
                    if itv["start_tick"] <= day_tick < itv["end_tick"]:
                        if cat in ["main_dish", "appetizer"]:
                            itv["completed_foods"] += 1
                        else:
                            itv["completed_drinks"] += 1
                        break

        # Track order queue entry and stage wait
        for order in self.engine.order_queue:
            if order.current_stage_idx < len(order.stages):
                stage = order.stages[order.current_stage_idx]
                st_type = stage.get("station_type", "PREP")
                self.station_type_total_demands[st_type] = self.station_type_total_demands.get(st_type, 0) + 1

                # Track queue wait duration
                order_key = f"{order.order_id}_{order.current_stage_idx}"
                if order_key not in self._order_stage_entry:
                    self._order_stage_entry[order_key] = tick
                else:
                    wait_so_far = tick - self._order_stage_entry[order_key]
                    if wait_so_far > 0 and wait_so_far % 5 == 0:
                        self.station_type_queue_waits[st_type].append(float(wait_so_far))

        # Check Station Fullness & Saturation vs Starvation
        available_chefs_count = sum(1 for c in self.engine.grid.chefs.values() if len(c.active_orders) < c.capacity and c.status != "COOKING")

        for st_type in self.station_type_blocked_ticks:
            stations_of_type = [s for s in self.engine.grid.stations.values() if s.type == st_type]
            if not stations_of_type:
                continue

            all_full = all(s.is_full or getattr(s, "is_broken", False) for s in stations_of_type)
            any_queued = any(
                o.current_stage_idx < len(o.stages) and o.stages[o.current_stage_idx].get("station_type") == st_type
                for o in self.engine.order_queue
            )

            if all_full and any_queued:
                self.station_type_blocked_ticks[st_type] += 1
                if available_chefs_count > 0:
                    # Chefs are ready but all stations are full -> Station capacity saturation!
                    self.station_type_saturation_ticks[st_type] += 1
            elif not all_full and any_queued and available_chefs_count == 0:
                # Stations have free space but no chef is available -> Chef shortage!
                self.station_type_starvation_ticks[st_type] += 1

        # Track Individual Stations
        for s_id, station in self.engine.grid.stations.items():
            if len(station.active_orders) > 0:
                self.station_busy_ticks[s_id] = self.station_busy_ticks.get(s_id, 0) + 1
            if station.is_full or getattr(station, "is_broken", False):
                self.station_full_ticks[s_id] = self.station_full_ticks.get(s_id, 0) + 1

        # Track Chefs
        for c_id, chef in self.engine.grid.chefs.items():
            if chef.status == "COOKING" or len(chef.active_orders) > 0:
                self.chef_busy_ticks[c_id] = self.chef_busy_ticks.get(c_id, 0) + 1
            elif chef.status in ["WALKING_TO_STATION", "DELIVERING_TO_COUNTER"]:
                self.chef_walking_ticks[c_id] = self.chef_walking_ticks.get(c_id, 0) + 1
            else:
                self.chef_idle_ticks[c_id] = self.chef_idle_ticks.get(c_id, 0) + 1

            if chef.current_task and chef.current_task.get("type") == "TRANSFER_STAGE":
                if chef.current_task.get("substate") == "PLACING_STAGE" and chef.current_task.get("finish_tick") == tick:
                    self.chef_stage_transfers[c_id] = self.chef_stage_transfers.get(c_id, 0) + 1

        # Track Waiters
        for w_id, waiter in self.engine.grid.waiters.items():
            if waiter.status == "DELIVERING" or (waiter.current_task and waiter.current_task.get("type") == "DELIVER"):
                self.waiter_deliver_ticks[w_id] = self.waiter_deliver_ticks.get(w_id, 0) + 1
            elif waiter.status == "TAKING_ORDER" or (waiter.current_task and waiter.current_task.get("type") == "TAKE_ORDER"):
                self.waiter_order_ticks[w_id] = self.waiter_order_ticks.get(w_id, 0) + 1
            elif waiter.status == "CLEANING" or (waiter.current_task and waiter.current_task.get("type") == "CLEAN_TABLE"):
                self.waiter_clean_ticks[w_id] = self.waiter_clean_ticks.get(w_id, 0) + 1
            else:
                self.waiter_idle_ticks[w_id] = self.waiter_idle_ticks.get(w_id, 0) + 1

            if waiter.current_task and waiter.current_task.get("type") == "TRANSFER_TAKEOUT_DRINK":
                if waiter.current_task.get("substate") == "WALK_TO_TAKEOUT" and not waiter.path:
                    self.waiter_drink_transfers[w_id] = self.waiter_drink_transfers.get(w_id, 0) + 1

        # Track Counters
        all_cnts = list(self.engine.grid.delivery_counters.values())
        if getattr(self.engine.grid, "takeout_counter", None):
            all_cnts.append(self.engine.grid.takeout_counter)
        if getattr(self.engine.grid, "beverage_counter", None):
            all_cnts.append(self.engine.grid.beverage_counter)

        for cnt in all_cnts:
            if cnt.is_full:
                self.counter_full_ticks[cnt.id] = self.counter_full_ticks.get(cnt.id, 0) + 1
            self.counter_total_dishes[cnt.id] = self.counter_total_dishes.get(cnt.id, 0) + len(cnt.ready_orders)

    def record_churn(self, table_status: str, count: int = 1, table=None):
        """Records churn with dish-type and waiting stage attribution."""
        day_tick = self.engine.tick % 1440
        if table_status in self.churn_reasons:
            self.churn_reasons[table_status] += count
        else:
            self.churn_reasons["WAITING_FOOD"] += count

        for itv in self.interval_metrics:
            if itv["start_tick"] <= day_tick < itv["end_tick"]:
                itv["churn_count"] += count
                break

        if table:
            for order in list(table.current_orders) + list(table.pending_orders):
                d_type = order.dish_type
                self.churn_by_dish[d_type] = self.churn_by_dish.get(d_type, 0) + 1
                self.dish_churns[d_type] = self.dish_churns.get(d_type, 0) + 1
                if order.current_stage_idx < len(order.stages):
                    curr_stage = order.stages[order.current_stage_idx].get("station_type", "UNKNOWN")
                    self.churn_by_stage[curr_stage] = self.churn_by_stage.get(curr_stage, 0) + 1

    def get_stage_queue_summary(self) -> List[Dict[str, Any]]:
        """Returns average queue wait time and total blockage per station type."""
        summary = []
        ticks = max(1, self.total_ticks_observed)
        for st_type, waits in self.station_type_queue_waits.items():
            stations = [s for s in self.engine.grid.stations.values() if s.type == st_type]
            total_cap = sum(s.capacity for s in stations)
            avg_wait = round(float(np.mean(waits)), 1) if waits else 0.0
            max_wait = round(float(np.max(waits)), 1) if waits else 0.0
            blocked_pct = round((self.station_type_blocked_ticks.get(st_type, 0) / ticks) * 100, 1)
            sat_pct = round((self.station_type_saturation_ticks.get(st_type, 0) / ticks) * 100, 1)
            starv_pct = round((self.station_type_starvation_ticks.get(st_type, 0) / ticks) * 100, 1)

            summary.append({
                "station_type": st_type,
                "station_count": len(stations),
                "total_capacity": total_cap,
                "avg_queue_wait_minutes": avg_wait,
                "max_queue_wait_minutes": max_wait,
                "blocked_percentage": blocked_pct,
                "station_saturation_percentage": sat_pct,
                "chef_starvation_percentage": starv_pct,
                "severity_score": round((avg_wait * 2.0) + (blocked_pct * 1.5), 1)
            })
        return sorted(summary, key=lambda x: x["severity_score"], reverse=True)

    def get_station_summary(self) -> List[Dict[str, Any]]:
        summary = []
        ticks = max(1, self.total_ticks_observed)
        for s_id, s in self.engine.grid.stations.items():
            busy_pct = round((self.station_busy_ticks.get(s_id, 0) / ticks) * 100, 1)
            full_pct = round((self.station_full_ticks.get(s_id, 0) / ticks) * 100, 1)
            summary.append({
                "id": s_id,
                "type": s.type,
                "capacity": s.capacity,
                "busy_percentage": busy_pct,
                "full_percentage": full_pct,
                "bottleneck_score": round((busy_pct * 0.4) + (full_pct * 0.6), 1)
            })
        return sorted(summary, key=lambda x: x["bottleneck_score"], reverse=True)

    def get_chef_summary(self) -> List[Dict[str, Any]]:
        summary = []
        ticks = max(1, self.total_ticks_observed)
        for c_id in self.engine.grid.chefs:
            busy_pct = round((self.chef_busy_ticks.get(c_id, 0) / ticks) * 100, 1)
            walk_pct = round((self.chef_walking_ticks.get(c_id, 0) / ticks) * 100, 1)
            idle_pct = round((self.chef_idle_ticks.get(c_id, 0) / ticks) * 100, 1)
            summary.append({
                "id": c_id,
                "busy_percentage": busy_pct,
                "walking_percentage": walk_pct,
                "idle_percentage": idle_pct,
                "total_work_load": round(busy_pct + walk_pct, 1)
            })
        return sorted(summary, key=lambda x: x["total_work_load"], reverse=True)

    def get_waiter_summary(self) -> List[Dict[str, Any]]:
        summary = []
        ticks = max(1, self.total_ticks_observed)
        for w_id in self.engine.grid.waiters:
            deliv_pct = round((self.waiter_deliver_ticks.get(w_id, 0) / ticks) * 100, 1)
            order_pct = round((self.waiter_order_ticks.get(w_id, 0) / ticks) * 100, 1)
            clean_pct = round((self.waiter_clean_ticks.get(w_id, 0) / ticks) * 100, 1)
            idle_pct = round((self.waiter_idle_ticks.get(w_id, 0) / ticks) * 100, 1)
            work_pct = round(deliv_pct + order_pct + clean_pct, 1)
            summary.append({
                "id": w_id,
                "deliver_percentage": deliv_pct,
                "order_percentage": order_pct,
                "clean_percentage": clean_pct,
                "idle_percentage": idle_pct,
                "total_work_load": work_pct
            })
        return sorted(summary, key=lambda x: x["total_work_load"], reverse=True)

    def get_counter_summary(self) -> List[Dict[str, Any]]:
        summary = []
        ticks = max(1, self.total_ticks_observed)
        all_cnts = list(self.engine.grid.delivery_counters.values())
        if getattr(self.engine.grid, "takeout_counter", None):
            all_cnts.append(self.engine.grid.takeout_counter)

        for c in all_cnts:
            full_pct = round((self.counter_full_ticks.get(c.id, 0) / ticks) * 100, 1)
            avg_load = round(self.counter_total_dishes.get(c.id, 0) / ticks, 2)
            summary.append({
                "id": c.id,
                "capacity": c.capacity,
                "full_percentage": full_pct,
                "avg_dishes_on_counter": avg_load
            })
        return sorted(summary, key=lambda x: x["full_percentage"], reverse=True)

    def get_top_bottlenecks(self, top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Synthesizes metrics across all subsystems and generates exact root causes and prescriptive fixes.
        """
        candidates = []

        # 1. Deep Station-Type Queue Bottlenecks
        stage_sums = self.get_stage_queue_summary()
        for st in stage_sums:
            if st["avg_queue_wait_minutes"] > 5.0 or st["blocked_percentage"] > 10.0:
                is_station_fault = (st["station_saturation_percentage"] > 0 and st["station_saturation_percentage"] >= st["chef_starvation_percentage"]) or st["blocked_percentage"] > 5.0
                if is_station_fault:
                    impact = f"{st['station_type']} istasyonları dolu olduğu için siparişler ortalama {st['avg_queue_wait_minutes']} dk bekliyor (Blokaj: %{st['blocked_percentage']})."
                    rec = f"Mevcut {st['station_count']} adet {st['station_type']} istasyonuna +2 istasyon ekleyin veya istasyon kapasitesini artırın."
                else:
                    impact = f"{st['station_type']} istasyonunda boş kapasite bulunmasına rağmen (Blokaj: %{st['blocked_percentage']}), aşçılar diğer siparişlerle meşgul olduğu veya algoritma diğer siparişlere öncelik verdiği için ortalama {st['avg_queue_wait_minutes']} dk bekleme oluşuyor."
                    rec = f"{st['station_type']} istasyon kapasitesi yeterlidir. Aşçı kadrosunu artırın veya çizelgeleme algoritması önceliklerini dengeleyin."

                candidates.append({
                    "category": f"MUTFAK İSTASYONU ({st['station_type']})",
                    "name": f"{st['station_type']} İstasyon Grubu ({st['station_count']} İstasyon, Toplam Kapasite: {st['total_capacity']})",
                    "severity": st["severity_score"],
                    "metric": f"Ort. Kuyruk Bekleme: {st['avg_queue_wait_minutes']} dk (Maks: {st['max_queue_wait_minutes']} dk) | %{st['blocked_percentage']} Süre Kilitli",
                    "impact": impact,
                    "recommendation": rec
                })

        # 2. Waiter Bottlenecks
        waiter_sums = self.get_waiter_summary()
        if waiter_sums:
            avg_waiter_work = float(np.mean([w["total_work_load"] for w in waiter_sums]))
            max_waiter = waiter_sums[0]
            if avg_waiter_work > 60.0 or max_waiter["total_work_load"] > 75.0:
                candidates.append({
                    "category": "PERSONEL (GARSON)",
                    "name": f"Garson Kadrosu (En Yoğun: {max_waiter['id']})",
                    "severity": max_waiter["total_work_load"],
                    "metric": f"Ort. %{avg_waiter_work:.1f} Yük (Maks: %{max_waiter['total_work_load']} - {max_waiter['id']})",
                    "impact": "Sipariş alma ve masa temizleme gecikiyor, müşteri sabrı tükeniyor.",
                    "recommendation": f"+{max(1, int(len(waiter_sums)*0.2))} Garson ekleyin veya masalara yakın dağıtın."
                })

        # 3. Chef Bottlenecks
        chef_sums = self.get_chef_summary()
        if chef_sums:
            avg_chef_work = float(np.mean([c["total_work_load"] for c in chef_sums]))
            max_chef = chef_sums[0]
            if avg_chef_work > 60.0:
                candidates.append({
                    "category": "PERSONEL (AŞÇI)",
                    "name": f"Aşçı Kadrosu (En Yoğun: {max_chef['id']})",
                    "severity": max_chef["total_work_load"],
                    "metric": f"Ort. %{avg_chef_work:.1f} Yük (Maks: %{max_chef['total_work_load']} - {max_chef['id']})",
                    "impact": "Aşçılar tüm vardiya boyunca aralıksız yemek hazırlıyor.",
                    "recommendation": f"+{max(1, int(len(chef_sums)*0.2))} Aşçı ekleyin."
                })

        # 4. Counter Bottlenecks
        counter_sums = self.get_counter_summary()
        for c in counter_sums:
            if c["full_percentage"] > 10.0:
                candidates.append({
                    "category": "TESLİMAT TEZGAHI",
                    "name": f"{c['id']}",
                    "severity": c["full_percentage"] * 1.2,
                    "metric": f"%{c['full_percentage']} Süre Doygun (Kapasite: {c['capacity']})",
                    "impact": "Aşçılar pişen yemekleri bırakamıyor, ocaklar kilitleniyor.",
                    "recommendation": "Teslimat tezgahı yuva sayısını artırın veya paket servis rafını ayırın."
                })

        # 5. Churn Attribution (Only Kitchen Cooked Dishes: Main Dish & Appetizer)
        total_churn = sum(self.churn_reasons.values())
        if total_churn > 0:
            food_churns = {d: cnt for d, cnt in self.churn_by_dish.items() if self.dish_categories.get(d) in ["main_dish", "appetizer"]}
            top_churn_dish = max(food_churns.items(), key=lambda x: x[1])[0] if food_churns else (max(self.churn_by_dish.items(), key=lambda x: x[1])[0] if self.churn_by_dish else "Bilinmiyor")
            
            valid_stages = {st: cnt for st, cnt in self.churn_by_stage.items() if st not in ["UNKNOWN", ""] and cnt > 0}
            top_churn_stage = max(valid_stages.items(), key=lambda x: x[1])[0] if valid_stages else "MUTFAK"

            if self.churn_reasons["WAITING_FOOD"] > total_churn * 0.3:
                candidates.append({
                    "category": "MÜŞTERİ KAYBI (CHURN)",
                    "name": f"Yemek Bekleme Kaybı (En Çok Etkilenen Yemek: {top_churn_dish}, Aşama: {top_churn_stage})",
                    "severity": (self.churn_reasons["WAITING_FOOD"] / total_churn) * 100,
                    "metric": f"{self.churn_reasons['WAITING_FOOD']} müşteri yemek beklerken ayrıldı (%{self.churn_reasons['WAITING_FOOD']/total_churn*100:.1f})",
                    "impact": f"Müşteriler en çok '{top_churn_dish}' yemeğini beklerken ve '{top_churn_stage}' istasyonunda kuyruk kilitlendiğinde sabırları tükendi.",
                    "recommendation": f"Öncelikle {top_churn_stage} istasyonlarının kapasitesini veya aşçı sayısını artırın."
                })

        candidates.sort(key=lambda x: x["severity"], reverse=True)
        return candidates[:top_n]

    def get_dish_performance_summary(self) -> List[Dict[str, Any]]:
        """
        Returns performance and bottleneck diagnostics grouped by individual dish type.
        """
        summary = []
        all_dishes = sorted(list(set(self.dish_demands.keys()) | set(self.dish_completions.keys()) | set(self.dish_churns.keys())))

        for d in all_dishes:
            completed = self.dish_completions.get(d, 0)
            churned = self.dish_churns.get(d, 0)
            demand = max(self.dish_demands.get(d, 0), completed + churned)
            cat = self.dish_categories.get(d, "main_dish")
            waits = self.dish_wait_times.get(d, [])
            cooks = self.dish_cook_times.get(d, [])
            colds = self.dish_cold_times.get(d, [])

            succ_rate = round((completed / max(1, demand)) * 100, 1) if demand > 0 else 0.0
            avg_wait = round(float(np.mean(waits)), 2) if waits else 0.0
            avg_cook = round(float(np.mean(cooks)), 2) if cooks else 0.0
            avg_cold = round(float(np.mean(colds)), 2) if colds else 0.0
            hot_rate = round((sum(1 for c in colds if c == 0.0) / max(1, len(colds))) * 100, 1) if colds else 100.0

            summary.append({
                "dish_type": d,
                "category": cat,
                "demand_count": demand,
                "completed_count": completed,
                "churn_count": churned,
                "success_rate": succ_rate,
                "avg_queue_wait_minutes": avg_wait,
                "avg_cook_minutes": avg_cook,
                "avg_cold_minutes": avg_cold,
                "hot_delivery_rate": hot_rate
            })

        # Sort: main_dish first, then appetizer, then beverage, within category by demand
        cat_order = {"main_dish": 1, "appetizer": 2, "beverage": 3}
        return sorted(summary, key=lambda x: (cat_order.get(x["category"], 9), -x["demand_count"]))

    def get_interval_summary(self) -> List[Dict[str, Any]]:
        """
        Returns hourly / interval breakdown of arrivals, completions, wait times, and churn.
        """
        summary = []
        for itv in self.interval_metrics:
            waits = itv["wait_times"]
            avg_w = round(float(np.mean(waits)), 2) if waits else 0.0
            summary.append({
                "description": itv["description"],
                "start_tick": itv["start_tick"],
                "end_tick": itv["end_tick"],
                "target_occupancy": itv["target_occupancy"],
                "completed_foods": itv["completed_foods"],
                "completed_drinks": itv["completed_drinks"],
                "total_completed": itv["completed_foods"] + itv["completed_drinks"],
                "churn_count": itv["churn_count"],
                "avg_wait_minutes": avg_w
            })
        return summary

    def get_staff_detailed_summary(self) -> Dict[str, Any]:
        """
        Returns full detailed operational staff task breakdown.
        """
        chefs = self.get_chef_summary()
        waiters = self.get_waiter_summary()

        for c in chefs:
            c["stage_transfers"] = self.chef_stage_transfers.get(c["id"], 0)

        for w in waiters:
            w["drink_transfers"] = self.waiter_drink_transfers.get(w["id"], 0)

        return {
            "chefs": chefs,
            "waiters": waiters
        }
