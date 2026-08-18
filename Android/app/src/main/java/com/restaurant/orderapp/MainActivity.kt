package com.restaurant.orderapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.restaurant.orderapp.ui.screens.OrderAppScreen
import com.restaurant.orderapp.ui.theme.DarkBackground
import com.restaurant.orderapp.ui.theme.RestaurantOrderAppTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            RestaurantOrderAppTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = DarkBackground
                ) {
                    OrderAppScreen()
                }
            }
        }
    }
}
