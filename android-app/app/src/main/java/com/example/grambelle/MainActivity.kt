package com.example.grambelle

import android.Manifest
import android.content.Context
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Bundle
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.example.grambelle.theme.GramBelleTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            GramBelleTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    GramBelleApp()
                }
            }
        }
    }
}

@Composable
fun GramBelleApp() {
    val context = LocalContext.current
    val sharedPref = remember { context.getSharedPreferences("GramBellePrefs", Context.MODE_PRIVATE) }
    
    var serverUrl by remember { mutableStateOf(sharedPref.getString("server_url", "") ?: "") }
    var inputUrl by remember { mutableStateOf(serverUrl) }
    var micPermissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { isGranted ->
            micPermissionGranted = isGranted
        }
    )

    // Request microphone permission on startup if not granted
    LaunchedEffect(Unit) {
        if (!micPermissionGranted) {
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    if (serverUrl.isEmpty()) {
        // Connection Screen UI
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp)
                .safeDrawingPadding(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                text = "Gram Belle",
                fontSize = 32.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            
            Text(
                text = "Companion Voice Assistant Client",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(bottom = 32.dp)
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier
                        .padding(20.dp)
                        .fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "Enter Gram Belle Server IP",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 16.sp,
                        modifier = Modifier.padding(bottom = 16.dp)
                    )

                    OutlinedTextField(
                        value = inputUrl,
                        onValueChange = { inputUrl = it },
                        label = { Text("PC IP Address (e.g. 192.168.1.100:8000)") },
                        placeholder = { Text("192.168.1.100:8000") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    Spacer(modifier = Modifier.height(20.dp))

                    Button(
                        onClick = {
                            var cleanUrl = inputUrl.trim()
                            if (cleanUrl.isNotEmpty()) {
                                if (!cleanUrl.startsWith("http://") && !cleanUrl.startsWith("https://")) {
                                    cleanUrl = "http://$cleanUrl"
                                }
                                sharedPref.edit().putString("server_url", cleanUrl).apply()
                                serverUrl = cleanUrl
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text("Connect", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }

            if (!micPermissionGranted) {
                Spacer(modifier = Modifier.height(24.dp))
                Text(
                    text = "⚠️ Microphone permission is required for voice turns.",
                    color = MaterialTheme.colorScheme.error,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium
                )
                Button(
                    onClick = { permissionLauncher.launch(Manifest.permission.RECORD_AUDIO) },
                    modifier = Modifier.padding(top = 8.dp)
                ) {
                    Text("Grant Permission")
                }
            }
        }
    } else {
        // WebView Screen UI
        Box(modifier = Modifier.fillMaxSize().safeDrawingPadding()) {
            AndroidView(
                factory = { ctx ->
                    WebView(ctx).apply {
                        settings.apply {
                            javaScriptEnabled = true
                            domStorageEnabled = true
                            mediaPlaybackRequiresUserGesture = false
                            allowFileAccess = true
                        }
                        webViewClient = object : WebViewClient() {
                            // Let the web view handle all redirects internally
                        }
                        webChromeClient = object : WebChromeClient() {
                            override fun onPermissionRequest(request: PermissionRequest) {
                                // Grant mic permission to web app
                                request.grant(request.resources)
                            }
                        }
                        loadUrl(serverUrl)
                    }
                },
                modifier = Modifier.fillMaxSize()
            )

            // Small Floating Action Button to Disconnect/Reconfigure
            FloatingActionButton(
                onClick = {
                    serverUrl = ""
                },
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(16.dp),
                containerColor = MaterialTheme.colorScheme.primaryContainer,
                contentColor = MaterialTheme.colorScheme.onPrimaryContainer
            ) {
                Text(
                    text = "⚙",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 8.dp)
                )
            }
        }
    }
}
