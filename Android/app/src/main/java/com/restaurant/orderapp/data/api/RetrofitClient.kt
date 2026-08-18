package com.restaurant.orderapp.data.api

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {

    private var currentBaseUrl: String = "http://10.0.2.2:8000/" // Android Emulator localhost
    private var apiService: RestaurantApiService? = null

    fun getBaseUrl(): String = currentBaseUrl

    fun updateBaseUrl(newIpOrUrl: String) {
        var formatted = newIpOrUrl.trim()
        if (!formatted.startsWith("http://") && !formatted.startsWith("https://")) {
            formatted = "http://$formatted"
        }
        if (!formatted.endsWith("/")) {
            formatted = "$formatted/"
        }
        currentBaseUrl = formatted
        apiService = createService(currentBaseUrl)
    }

    fun getService(): RestaurantApiService {
        if (apiService == null) {
            apiService = createService(currentBaseUrl)
        }
        return apiService!!
    }

    private fun createService(baseUrl: String): RestaurantApiService {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val okHttpClient = OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .build()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(RestaurantApiService::class.java)
    }
}
