package com.restaurant.orderapp.data.models

import com.google.gson.annotations.SerializedName

data class TableDto(
    @SerializedName("id") val id: String,
    @SerializedName("capacity") val capacity: Int,
    @SerializedName("status") val status: String, // EMPTY, WAITING_FOOD, EATING
    @SerializedName("customers") val customers: Int = 0,
    @SerializedName("patience") val patience: Float = 30.0f
)

data class DishStageDto(
    @SerializedName("station_type") val stationType: String,
    @SerializedName("time") val time: Float
)

data class DishDto(
    @SerializedName("type") val type: String,
    @SerializedName("name") val name: String,
    @SerializedName("stages") val stages: List<DishStageDto>,
    @SerializedName("price") val price: Double = 0.0,
    @SerializedName("icon") val icon: String = "🍽️"
)

data class OrderItemDto(
    @SerializedName("dish_type") val dishType: String,
    @SerializedName("quantity") val quantity: Int = 1,
    @SerializedName("note") val note: String = ""
)

data class OrderCreateRequest(
    @SerializedName("table_id") val tableId: String?, // null ise Takeout
    @SerializedName("is_takeout") val isTakeout: Boolean = false,
    @SerializedName("items") val items: List<OrderItemDto>
)

data class OrderItemResponseDto(
    @SerializedName("order_id") val orderId: String,
    @SerializedName("table_id") val tableId: String?,
    @SerializedName("dish_type") val dishType: String,
    @SerializedName("status") val status: String, // QUEUED_STAGE, PREPARING, READY, DELIVERING, SERVED
    @SerializedName("current_stage") val currentStage: String?,
    @SerializedName("assigned_station") val assignedStation: String?,
    @SerializedName("assigned_chef") val assignedChef: String?,
    @SerializedName("assigned_waiter") val assignedWaiter: String?,
    @SerializedName("predicted_time") val predictedTime: Float?,
    @SerializedName("is_takeout") val isTakeout: Boolean = false
)

data class OrderCreateResponse(
    @SerializedName("status") val status: String,
    @SerializedName("message") val message: String,
    @SerializedName("created_orders") val createdOrders: List<OrderItemResponseDto>
)

data class SystemStatusDto(
    @SerializedName("tick") val tick: Int,
    @SerializedName("active_queue_count") val activeQueueCount: Int,
    @SerializedName("completed_count") val completedCount: Int,
    @SerializedName("churned_count") val churnedCount: Int,
    @SerializedName("mode") val mode: String = "RL"
)
