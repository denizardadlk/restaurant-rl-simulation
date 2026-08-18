package com.restaurant.orderapp.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val DarkBackground = Color(0xFF10141D)
val SurfaceCard = Color(0xFF1B2232)
val SurfaceCardHover = Color(0xFF252F45)
val AccentOrange = Color(0xFFFF8A00)
val AccentOrangeLight = Color(0xFFFFAB40)
val TextPrimary = Color(0xFFF1F5F9)
val TextSecondary = Color(0xFF94A3B8)
val StatusGreen = Color(0xFF10B981)
val StatusYellow = Color(0xFFF59E0B)
val StatusRed = Color(0xFFEF4444)
val StatusBlue = Color(0xFF3B82F6)

private val DarkColorScheme = darkColorScheme(
    primary = AccentOrange,
    onPrimary = Color.White,
    secondary = AccentOrangeLight,
    background = DarkBackground,
    surface = SurfaceCard,
    onBackground = TextPrimary,
    onSurface = TextPrimary
)

@Composable
fun RestaurantOrderAppTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
