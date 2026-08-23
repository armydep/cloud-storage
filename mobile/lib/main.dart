import 'package:cloudestorage/app/app.dart';
import 'package:cloudestorage/core/config/app_config.dart';
import 'package:cloudestorage/features/push/data/push_background_handler.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'features/auth/application/auth_providers.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  try {
    await Firebase.initializeApp();
    // Must be registered before runApp, and must reference a top-level
    // function -- the plugin spawns a separate isolate for it, which is why
    // firebaseMessagingBackgroundHandler cannot be a closure or a method.
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
  } on Object catch (e) {
    // Push registration becomes unavailable, but nothing else about the app
    // depends on Firebase -- login, browsing and uploads must keep working
    // regardless of whether this succeeds.
    debugPrint('Firebase initialization failed: $e');
  }

  runApp(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(AppConfig.fromEnvironment()),
      ],
      child: const CloudStorageApp(),
    ),
  );
}
