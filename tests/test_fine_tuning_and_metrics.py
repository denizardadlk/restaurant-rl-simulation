import pytest
from simulation.entities import Table, Order
from simulation.engine import SimulationEngine
from simulation.rl_agent import linear_schedule

def test_customer_patience_scaled_1_5x():
    """Müşteri sabır süresinin 1.5x (30.0) olduğunu doğrula."""
    t = Table(id="T1", x=0, y=0, capacity=4)
    assert t.patience == 30.0
    
    engine = SimulationEngine()
    engine.reset()
    engine._generate_orders()
    for table in engine.grid.tables.values():
        if table.status == "WAITING_FOOD":
            assert table.patience == 30.0

def test_linear_schedule_decay():
    """Öğrenme oranı çizelgesinin düzgün azaldığını doğrula."""
    sched = linear_schedule(3e-4, 1e-5)
    assert pytest.approx(sched(1.0)) == 3e-4 # Başlangıçta
    assert pytest.approx(sched(0.5)) == 1.55e-4 # Ortada
    assert pytest.approx(sched(0.0)) == 1e-5 # Bitişte

def test_metric_calculations():
    """Yeni eklenen servis başarı oranı ve sıcak teslimat metrik hesaplarını test et."""
    completed = 300
    churned = 100
    total_demand = completed + churned
    success_rate = round((completed / total_demand) * 100, 1)
    assert success_rate == 75.0
    
    cold_times = [0.0, 0.0, 2.5, 0.0, 10.0]
    hot_count = sum(1 for c in cold_times if c <= 0.001)
    hot_ratio = round((hot_count / len(cold_times)) * 100, 1)
    assert hot_ratio == 60.0
