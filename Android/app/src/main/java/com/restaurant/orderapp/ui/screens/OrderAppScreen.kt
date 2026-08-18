package com.restaurant.orderapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.restaurant.orderapp.data.api.RetrofitClient
import com.restaurant.orderapp.data.models.*
import com.restaurant.orderapp.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OrderAppScreen() {
    val coroutineScope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    var selectedTab by remember { mutableIntStateOf(0) } // 0: Masalar, 1: Menü, 2: Canlı Takip
    var serverIp by remember { mutableStateOf(RetrofitClient.getBaseUrl()) }
    var showIpDialog by remember { mutableStateOf(false) }

    // App State
    var tables by remember { mutableStateOf<List<TableDto>>(emptyList()) }
    var menu by remember { mutableStateOf<List<DishDto>>(emptyList()) }
    var activeOrders by remember { mutableStateOf<List<OrderItemResponseDto>>(emptyList()) }
    var systemStatus by remember { mutableStateOf<SystemStatusDto?>(null) }
    var isRefreshing by remember { mutableStateOf(false) }

    // Active Selection State
    var selectedTableId by remember { mutableStateOf<String?>("T1") }
    var isTakeout by remember { mutableStateOf(false) }
    val cartItems = remember { mutableStateMapOf<String, Int>() } // dishType -> quantity

    // Initial default menu if server is not yet reachable
    val fallbackMenu = listOf(
        DishDto("Pizza", "Taş Fırın Pizza", listOf(DishStageDto("PREP", 4f), DishStageDto("OVEN", 10f)), 180.0, "🍕"),
        DishDto("Burger", "Gurme Burger", listOf(DishStageDto("PREP", 2f), DishStageDto("STOVE", 8f)), 160.0, "🍔"),
        DishDto("Steak", "Dana Antrikot", listOf(DishStageDto("PREP", 2f), DishStageDto("GRILL", 15f)), 320.0, "🥩"),
        DishDto("Salad", "Akdeniz Salatası", listOf(DishStageDto("PREP", 5f)), 90.0, "🥗")
    )

    fun fetchAllData() {
        coroutineScope.launch {
            isRefreshing = true
            try {
                withContext(Dispatchers.IO) {
                    val tResp = RetrofitClient.getService().getTables()
                    if (tResp.isSuccessful && tResp.body() != null) {
                        tables = tResp.body()!!
                    }
                    val mResp = RetrofitClient.getService().getMenu()
                    if (mResp.isSuccessful && mResp.body() != null) {
                        menu = mResp.body()!!
                    } else if (menu.isEmpty()) {
                        menu = fallbackMenu
                    }
                    val oResp = RetrofitClient.getService().getActiveOrders()
                    if (oResp.isSuccessful && oResp.body() != null) {
                        activeOrders = oResp.body()!!
                    }
                    val sResp = RetrofitClient.getService().getSystemStatus()
                    if (sResp.isSuccessful && sResp.body() != null) {
                        systemStatus = sResp.body()!!
                    }
                }
            } catch (e: Exception) {
                if (menu.isEmpty()) menu = fallbackMenu
            } finally {
                isRefreshing = false
            }
        }
    }

    // Auto-polling every 3 seconds
    LaunchedEffect(Unit) {
        fetchAllData()
        while (true) {
            delay(3000)
            fetchAllData()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "AI Restoran Sipariş Terminali",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        Text(
                            text = if (systemStatus != null) "Sistem Tick: ${systemStatus!!.tick} | Kuyruk: ${systemStatus!!.activeQueueCount}" else "Sunucu: $serverIp",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = SurfaceCard
                ),
                actions = {
                    IconButton(onClick = { fetchAllData() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Yenile", tint = AccentOrange)
                    }
                    IconButton(onClick = { showIpDialog = true }) {
                        Icon(Icons.Default.Settings, contentDescription = "Sunucu IP", tint = TextPrimary)
                    }
                }
            )
        },
        bottomBar = {
            NavigationBar(
                containerColor = SurfaceCard
            ) {
                NavigationBarItem(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    icon = { Icon(Icons.Default.TableRestaurant, contentDescription = "Masalar") },
                    label = { Text("Masalar") },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = AccentOrange,
                        selectedTextColor = AccentOrange,
                        indicatorColor = SurfaceCardHover
                    )
                )
                NavigationBarItem(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    icon = {
                        BadgedBox(
                            badge = {
                                val count = cartItems.values.sum()
                                if (count > 0) {
                                    Badge(containerColor = AccentOrange) { Text("$count") }
                                }
                            }
                        ) {
                            Icon(Icons.Default.RestaurantMenu, contentDescription = "Menü & Sipariş")
                        }
                    },
                    label = { Text("Menü & Sipariş") },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = AccentOrange,
                        selectedTextColor = AccentOrange,
                        indicatorColor = SurfaceCardHover
                    )
                )
                NavigationBarItem(
                    selected = selectedTab == 2,
                    onClick = { selectedTab = 2 },
                    icon = {
                        BadgedBox(
                            badge = {
                                if (activeOrders.isNotEmpty()) {
                                    Badge(containerColor = StatusBlue) { Text("${activeOrders.size}") }
                                }
                            }
                        ) {
                            Icon(Icons.Default.FormatListBulleted, contentDescription = "Aktif Takip")
                        }
                    },
                    label = { Text("Aşçı & Takip") },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = AccentOrange,
                        selectedTextColor = AccentOrange,
                        indicatorColor = SurfaceCardHover
                    )
                )
            }
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(DarkBackground)
                .padding(paddingValues)
        ) {
            when (selectedTab) {
                0 -> TablesScreen(
                    tables = if (tables.isEmpty()) getMockTables() else tables,
                    selectedTableId = selectedTableId,
                    onSelectTable = { tableId ->
                        selectedTableId = tableId
                        isTakeout = false
                        selectedTab = 1
                    },
                    onSelectTakeout = {
                        isTakeout = true
                        selectedTableId = null
                        selectedTab = 1
                    }
                )
                1 -> MenuOrderScreen(
                    menu = if (menu.isEmpty()) fallbackMenu else menu,
                    cartItems = cartItems,
                    selectedTableId = selectedTableId,
                    isTakeout = isTakeout,
                    onToggleTakeout = { isTakeout = it },
                    onChangeTable = { selectedTab = 0 },
                    onSendOrder = {
                        coroutineScope.launch {
                            val itemsList = cartItems.filter { it.value > 0 }.map { (dish, qty) ->
                                OrderItemDto(dishType = dish, quantity = qty)
                            }
                            if (itemsList.isEmpty()) {
                                snackbarHostState.showSnackbar("Lütfen en az 1 yemek seçin!")
                                return@launch
                            }
                            val req = OrderCreateRequest(
                                tableId = if (isTakeout) null else selectedTableId,
                                isTakeout = isTakeout,
                                items = itemsList
                            )
                            try {
                                val resp = withContext(Dispatchers.IO) {
                                    RetrofitClient.getService().createOrder(req)
                                }
                                if (resp.isSuccessful) {
                                    cartItems.clear()
                                    snackbarHostState.showSnackbar("🚀 Sipariş simülasyon sistemine aktarıldı!")
                                    selectedTab = 2
                                    fetchAllData()
                                } else {
                                    snackbarHostState.showSnackbar("Hata: ${resp.message()}")
                                }
                            } catch (e: Exception) {
                                snackbarHostState.showSnackbar("Sunucuya bağlanılamadı: ${e.localizedMessage}")
                            }
                        }
                    }
                )
                2 -> LiveTrackerScreen(
                    orders = activeOrders,
                    onRefresh = { fetchAllData() }
                )
            }
        }

        // Server IP Settings Dialog
        if (showIpDialog) {
            var tempIp by remember { mutableStateOf(serverIp) }
            AlertDialog(
                onDismissRequest = { showIpDialog = false },
                title = { Text("Host PC Sunucu Adresi") },
                text = {
                    Column {
                        Text(
                            "Ana bilgisayarın yerel IP adresini girin (Örn: http://192.168.1.100:8000 veya Emülatör için http://10.0.2.2:8000):",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedTextField(
                            value = tempIp,
                            onValueChange = { tempIp = it },
                            label = { Text("Sunucu URL / IP") },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = AccentOrange,
                                unfocusedBorderColor = TextSecondary
                            )
                        )
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            RetrofitClient.updateBaseUrl(tempIp)
                            serverIp = RetrofitClient.getBaseUrl()
                            showIpDialog = false
                            fetchAllData()
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = AccentOrange)
                    ) {
                        Text("Kaydet & Bağlan")
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showIpDialog = false }) {
                        Text("İptal", color = TextSecondary)
                    }
                },
                containerColor = SurfaceCard
            )
        }
    }
}

// -------------------------------------------------------------
// SCREEN 1: TABLES SELECTION
// -------------------------------------------------------------
@Composable
fun TablesScreen(
    tables: List<TableDto>,
    selectedTableId: String?,
    onSelectTable: (String) -> Unit,
    onSelectTakeout: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Restoran Masaları",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )

            Button(
                onClick = onSelectTakeout,
                colors = ButtonDefaults.buttonColors(containerColor = StatusBlue),
                shape = RoundedCornerShape(8.dp)
            ) {
                Icon(Icons.Default.DeliveryDining, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text("Paket Sipariş (Takeout)")
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(tables) { table ->
                val isSelected = table.id == selectedTableId
                val statusColor = when (table.status) {
                    "EMPTY" -> StatusGreen
                    "WAITING_FOOD" -> StatusYellow
                    else -> StatusBlue
                }

                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .border(
                            width = if (isSelected) 2.dp else 1.dp,
                            color = if (isSelected) AccentOrange else Color.Transparent,
                            shape = RoundedCornerShape(12.dp)
                        )
                        .clickable { onSelectTable(table.id) },
                    colors = CardDefaults.cardColors(
                        containerColor = if (isSelected) SurfaceCardHover else SurfaceCard
                    )
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "Masa ${table.id}",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary
                            )
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(statusColor.copy(alpha = 0.2f))
                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text = when (table.status) {
                                        "EMPTY" -> "BOŞ"
                                        "WAITING_FOOD" -> "YEMEK BEKLİYOR"
                                        "EATING" -> "YİYOR"
                                        else -> table.status
                                    },
                                    style = MaterialTheme.typography.labelSmall,
                                    color = statusColor,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "Kapasite: ${table.capacity} Kişilik",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )

                        if (table.status == "WAITING_FOOD") {
                            Spacer(modifier = Modifier.height(6.dp))
                            LinearProgressIndicator(
                                progress = { (table.patience / 30f).coerceIn(0f, 1f) },
                                modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)),
                                color = if (table.patience < 10f) StatusRed else StatusYellow,
                                trackColor = DarkBackground
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "Sabır: ${table.patience.toInt()} dk",
                                style = MaterialTheme.typography.labelSmall,
                                color = TextSecondary
                            )
                        }
                    }
                }
            }
        }
    }
}

// -------------------------------------------------------------
// SCREEN 2: MENU & ORDER ENTRY
// -------------------------------------------------------------
@Composable
fun MenuOrderScreen(
    menu: List<DishDto>,
    cartItems: MutableMap<String, Int>,
    selectedTableId: String?,
    isTakeout: Boolean,
    onToggleTakeout: (Boolean) -> Unit,
    onChangeTable: () -> Unit,
    onSendOrder: () -> Unit
) {
    val totalCount = cartItems.values.sum()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        // Table / Target Header
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = SurfaceCard),
            shape = RoundedCornerShape(12.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = if (isTakeout) "📦 Paket Sipariş (Takeout / Kurye)" else "🪑 Hedef: Masa ${selectedTableId ?: "Seçilmedi"}",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = AccentOrange
                    )
                    Text(
                        text = "Sipariş doğrudan ana simülasyona aktarılacaktır",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextSecondary
                    )
                }
                Button(
                    onClick = onChangeTable,
                    colors = ButtonDefaults.buttonColors(containerColor = SurfaceCardHover),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("Değiştir", color = TextPrimary)
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Dishes List
        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(menu) { dish ->
                val qty = cartItems[dish.type] ?: 0
                val prepTime = dish.stages.sumOf { it.time.toDouble() }

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = SurfaceCard),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(text = dish.icon, fontSize = 32.sp)
                            Spacer(modifier = Modifier.width(12.dp))
                            Column {
                                Text(
                                    text = dish.name,
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = TextPrimary
                                )
                                Text(
                                    text = "Pişirme: ~${prepTime.toInt()} dk | Aşamalar: ${dish.stages.joinToString(" ➔ ") { it.stationType }}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary
                                )
                            }
                        }

                        // Counter Controls
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            IconButton(
                                onClick = {
                                    if (qty > 0) cartItems[dish.type] = qty - 1
                                }
                            ) {
                                Icon(Icons.Default.RemoveCircleOutline, contentDescription = "Azalt", tint = TextSecondary)
                            }
                            Text(
                                text = "$qty",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = if (qty > 0) AccentOrange else TextPrimary,
                                modifier = Modifier.padding(horizontal = 4.dp)
                            )
                            IconButton(
                                onClick = {
                                    cartItems[dish.type] = qty + 1
                                }
                            ) {
                                Icon(Icons.Default.AddCircle, contentDescription = "Arttır", tint = AccentOrange)
                            }
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Send Order Action Button
        Button(
            onClick = onSendOrder,
            modifier = Modifier
                .fillMaxWidth()
                .height(54.dp),
            colors = ButtonDefaults.buttonColors(containerColor = AccentOrange),
            shape = RoundedCornerShape(12.dp),
            enabled = totalCount > 0
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Send, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Siparişi Simülasyona Gönder ($totalCount Adet)",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

// -------------------------------------------------------------
// SCREEN 3: LIVE ORDER & KITCHEN TRACKER
// -------------------------------------------------------------
@Composable
fun LiveTrackerScreen(
    orders: List<OrderItemResponseDto>,
    onRefresh: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Mutfak & Aşçı Atama Takibi",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Text(
                text = "Toplam: ${orders.size} Sipariş",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        if (orders.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Default.CheckCircleOutline, contentDescription = null, tint = StatusGreen, modifier = Modifier.size(56.dp))
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Kuyrukta aktif sipariş yok", color = TextPrimary, fontWeight = FontWeight.Bold)
                    Text("Yeni bir sipariş girdiğinizde aşçı ataması burada görünecektir.", color = TextSecondary, style = MaterialTheme.typography.bodySmall)
                }
            }
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(orders) { order ->
                    val statusColor = when (order.status) {
                        "QUEUED", "QUEUED_STAGE" -> StatusYellow
                        "PREPARING" -> AccentOrange
                        "READY" -> StatusGreen
                        "DELIVERING" -> StatusBlue
                        else -> TextSecondary
                    }

                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = SurfaceCard),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        text = if (order.isTakeout) "📦 Takeout" else "Masa ${order.tableId}",
                                        fontWeight = FontWeight.Bold,
                                        color = TextPrimary,
                                        style = MaterialTheme.typography.titleMedium
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        text = "#${order.orderId}",
                                        color = TextSecondary,
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }

                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(4.dp))
                                        .background(statusColor.copy(alpha = 0.2f))
                                        .padding(horizontal = 8.dp, vertical = 3.dp)
                                    ) {
                                    Text(
                                        text = order.status,
                                        color = statusColor,
                                        fontWeight = FontWeight.Bold,
                                        style = MaterialTheme.typography.labelSmall
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "Yemek: ${order.dishType} ${if (order.currentStage != null) "(${order.currentStage})" else ""}",
                                style = MaterialTheme.typography.bodyMedium,
                                color = TextPrimary
                            )

                            Spacer(modifier = Modifier.height(4.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "İstasyon: ${order.assignedStation ?: 'Bekliyor'} | Aşçı: ${order.assignedChef ?: 'Atanıyor'}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary
                                )
                                if (order.predictedTime != null) {
                                    Text(
                                        text = "ML ETA: ${String.format("%.1f", order.predictedTime)} dk",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = AccentOrangeLight,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// Fallback mock tables if offline
fun getMockTables(): List<TableDto> = listOf(
    TableDto("T1", 4, "EMPTY"),
    TableDto("T2", 2, "EMPTY"),
    TableDto("T3", 4, "EMPTY"),
    TableDto("T4", 2, "EMPTY"),
    TableDto("T5", 6, "EMPTY")
)
