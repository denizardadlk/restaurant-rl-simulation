import streamlit as st
import pandas as pd
import numpy as np
import time
import os
import plotly.express as px
import plotly.graph_objects as go

from simulation.engine import SimulationEngine
from simulation.gym_env import RestaurantGymEnv
from simulation.scheduler_baselines import FIFOScheduler, SPTScheduler

st.set_page_config(page_title="Restoran Simülasyon Dashboard", layout="wide")

st.title("🍽️ Yapay Zeka Destekli Dinamik Restoran Simülasyonu")

st.sidebar.header("Kontroller")

base_dir = os.path.dirname(os.path.abspath(__file__))
available_layouts = []
for folder in ["layouts", "config"]:
    f_dir = os.path.join(base_dir, folder)
    if os.path.exists(f_dir):
        for f in os.listdir(f_dir):
            if f.endswith(".json") and f not in available_layouts:
                available_layouts.append(f)

if not available_layouts:
    available_layouts = ["custom_layout.json", "default_layout.json"]

selected_layout = st.sidebar.selectbox("Layout Seçimi", available_layouts)
layout_path = os.path.join(base_dir, "layouts", selected_layout)
if not os.path.exists(layout_path):
    layout_path = os.path.join(base_dir, "config", selected_layout)

# Session State for engine
if 'engine' not in st.session_state or st.session_state.get('current_layout') != selected_layout:
    st.session_state.engine = SimulationEngine(layout_path)
    st.session_state.engine.reset()
    st.session_state.current_layout = selected_layout

if st.sidebar.button("Simülasyonu Sıfırla"):
    st.session_state.engine.reset()
    st.rerun()
    
sim_steps = st.sidebar.slider("Kaç Tick İlerletilsin?", 10, 1440, 100)

if st.sidebar.button("İlerlet"):
    with st.spinner(f"{sim_steps} adım koşturuluyor..."):
        for _ in range(sim_steps):
            st.session_state.engine.step()

# Main Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Tick (Zaman)", st.session_state.engine.tick)
col2.metric("Tamamlanan Sipariş", len(st.session_state.engine.completed_orders))
col3.metric("Churned Müşteri", st.session_state.engine.churned_customers)
col4.metric("Kuyruktaki Siparişler", len(st.session_state.engine.order_queue))

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["Canlı Simülasyon & Grid Durumu", "Model 1 (ML) Analizi", "RL / Schedulers Karşılaştırması", "Layout Düzenleyici"])

with tab1:
    st.subheader("Anlık Grid ve İstasyon Durumu")
    
    st.markdown(f"**ML Eğitim Verisi Büyüklüğü:** {st.session_state.engine.predictor.training_count}")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.write("Masalar:")
        table_data = []
        for t in st.session_state.engine.grid.tables.values():
            table_data.append({
                "Masa ID": t.id, 
                "Müşteri": t.customers, 
                "Sabır %": round(t.patience, 1),
                "Durum": "Dolu" if t.customers > 0 else "Boş"
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)
        
    with c2:
        st.write("İstasyonlar:")
        station_data = []
        for s in st.session_state.engine.grid.stations.values():
            station_data.append({
                "İstasyon": s.id, 
                "Yük": f"{len(s.active_orders)} / {s.capacity}"
            })
        st.dataframe(pd.DataFrame(station_data), use_container_width=True)

with tab2:
    st.subheader("Pişirme Süresi Tahmin Performansı (MAE)")
    
    orders = st.session_state.engine.completed_orders
    if len(orders) > 0:
        maes = []
        theo_maes = []
        for i, o in enumerate(orders):
            if o.actual_target_time:
                theo_err = abs(o.theoretical_time - o.actual_target_time)
                pred_err = abs((o.predicted_time if o.predicted_time else o.theoretical_time) - o.actual_target_time)
                theo_maes.append(theo_err)
                maes.append(pred_err)
                
        df_mae = pd.DataFrame({
            "Sipariş No": range(1, len(maes) + 1),
            "Teorik Süre Hatası": [np.mean(theo_maes[:i+1]) for i in range(len(theo_maes))],
            "ML Tahmin Hatası (MAE)": [np.mean(maes[:i+1]) for i in range(len(maes))]
        })
        
        fig = px.line(df_mae, x="Sipariş No", y=["Teorik Süre Hatası", "ML Tahmin Hatası (MAE)"], title="Kümülatif Ortalama Mutlak Hata (MAE)")
        st.plotly_chart(fig, use_container_width=True)
        
        # JIT Waiter - Cold time analysis
        st.subheader("JIT Garson Servis Gecikmesi (Yemek Soğuma Süresi)")
        cold_times = []
        for o in orders:
            if o.timestamps.get("kitchen_finish") and o.timestamps.get("delivered_at"):
                cold_time = max(0, o.timestamps["delivered_at"] - o.timestamps["kitchen_finish"] - 5) # minus standard delivery time
                cold_times.append(cold_time)
        
        if cold_times:
            df_cold = pd.DataFrame({"Sipariş": range(len(cold_times)), "Gecikme (tick)": cold_times})
            fig2 = px.scatter(df_cold, x="Sipariş", y="Gecikme (tick)", title="Sipariş Başına Tezgahta Bekleme (Soğuma) Süresi")
            st.plotly_chart(fig2, use_container_width=True)
            
    else:
        st.info("Yeterli tamamlanmış sipariş verisi yok. Simülasyonu ilerletin.")

with tab3:
    st.subheader("Algoritma Karşılaştırması (1 Günlük Koşu Sonuçları)")
    st.write("Aşağıdaki butonla FIFO ve SPT kural tabanlı algoritmaları 1440 tick boyunca koşturup karşılaştırabilirsiniz.")
    
    if st.button("Hızlı Karşılaştırma Çalıştır (FIFO vs SPT)"):
        with st.spinner("Değerlendiriliyor..."):
            env = RestaurantGymEnv(os.path.join(base_dir, "config", selected_layout))
            
            # FIFO
            env.reset()
            fifo_sched = FIFOScheduler(env.engine)
            done = False
            while not done:
                acts = fifo_sched.step()
                env._apply_manual_actions(acts)
                _, r, t, tr, info_fifo = env.step(0)
                done = t or tr
                
            # SPT
            env.reset()
            spt_sched = SPTScheduler(env.engine)
            done = False
            while not done:
                acts = spt_sched.step()
                env._apply_manual_actions(acts)
                _, r, t, tr, info_spt = env.step(0)
                done = t or tr
                
            comp_df = pd.DataFrame({
                "Metrik": ["Tamamlanan Sipariş", "Churned Müşteri"],
                "FIFO": [info_fifo["completed"], info_fifo["churned"]],
                "SPT": [info_spt["completed"], info_spt["churned"]]
            })
            
            st.table(comp_df)
            
            fig = px.bar(comp_df, x="Metrik", y=["FIFO", "SPT"], barmode="group", title="Performans Karşılaştırması")
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("PPO RL ajanı tam eğitim (100k+ step) gerektirdiği için bu hızlı teste dahil edilmemiştir.")

with tab4:
    st.subheader("Web Tabanlı Layout Düzenleyici")
    st.markdown("""
    Restoran haritasını, masaları, mutfak istasyonlarını ve personel sayılarını **sürükle-bırak** ve görsel arayüzle düzenlemek için yeni **Layout Düzenleyici** aracımızı kullanabilirsiniz.
    
    Çalıştırmak için yeni bir terminal açıp aşağıdaki komutu girin:
    ```bash
    python layout_editor.py
    ```
    Ardından tarayıcınızdan **http://localhost:8080/layout_editor.html** adresine giderek düzenleyiciye erişebilirsiniz.
    Kaydettiğiniz düzenler otomatik olarak `config/custom_layout.json` dosyasına yazılır.
    """)
