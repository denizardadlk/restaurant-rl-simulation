package com.restaurant.orderapp.data.api

import com.restaurant.orderapp.data.models.*
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface RestaurantApiService {

    @GET("/api/tables")
    suspend fun getTables(): Response<List<TableDto>>

    @GET("/api/menu")
    suspend fun getMenu(): Response<List<DishDto>>

    @POST("/api/orders")
    suspend fun createOrder(@Body request: OrderCreateRequest): Response<OrderCreateResponse>

    @GET("/api/orders/active")
    suspend fun getActiveOrders(): Response<List<OrderItemResponseDto>>

    @GET("/api/system/status")
    suspend fun getSystemStatus(): Response<SystemStatusDto>
}
