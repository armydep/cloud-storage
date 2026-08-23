import 'dart:async';

import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/push/application/push_providers.dart';
import 'package:cloudestorage/features/push/data/fcm_client.dart';
import 'package:cloudestorage/features/push/data/push_repository.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('registers the initial token on first watch', () async {
    final fcm = _FakeFcmClient()..token = 'initial-token';
    final repository = _FakePushRepository();
    final container = ProviderContainer(
      overrides: [
        fcmClientProvider.overrideWithValue(fcm),
        pushRepositoryProvider.overrideWithValue(repository),
      ],
    );
    addTearDown(container.dispose);

    final subscription = container.listen(
      pushDeviceRegistrationProvider,
      (_, _) {},
    );
    addTearDown(subscription.close);
    await Future<void>.delayed(Duration.zero);

    expect(repository.registerCalls, [
      {'token': 'initial-token', 'platform': 'android'},
    ]);
  });

  test('re-registers when the FCM token refreshes', () async {
    final fcm = _FakeFcmClient()..token = 'initial-token';
    final repository = _FakePushRepository();
    final container = ProviderContainer(
      overrides: [
        fcmClientProvider.overrideWithValue(fcm),
        pushRepositoryProvider.overrideWithValue(repository),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(
      pushDeviceRegistrationProvider,
      (_, _) {},
    );
    addTearDown(subscription.close);
    await Future<void>.delayed(Duration.zero);

    fcm.emitRefresh('refreshed-token');
    await Future<void>.delayed(Duration.zero);

    expect(repository.registerCalls, [
      {'token': 'initial-token', 'platform': 'android'},
      {'token': 'refreshed-token', 'platform': 'android'},
    ]);
  });

  test('a registration failure does not throw', () async {
    final fcm = _FakeFcmClient()..token = 'initial-token';
    final repository = _FakePushRepository()
      ..nextRegisterError = Exception('boom');
    final container = ProviderContainer(
      overrides: [
        fcmClientProvider.overrideWithValue(fcm),
        pushRepositoryProvider.overrideWithValue(repository),
      ],
    );
    addTearDown(container.dispose);

    expect(
      () => container.listen(pushDeviceRegistrationProvider, (_, _) {}),
      returnsNormally,
    );
    await Future<void>.delayed(Duration.zero);
  });

  test('does nothing when no token is available', () async {
    final fcm = _FakeFcmClient()..token = null;
    final repository = _FakePushRepository();
    final container = ProviderContainer(
      overrides: [
        fcmClientProvider.overrideWithValue(fcm),
        pushRepositoryProvider.overrideWithValue(repository),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(
      pushDeviceRegistrationProvider,
      (_, _) {},
    );
    addTearDown(subscription.close);
    await Future<void>.delayed(Duration.zero);

    expect(repository.registerCalls, isEmpty);
  });

  test(
    'a foreground message does not throw and does not touch the repository',
    () async {
      // Decision 14: firebase_messaging delivers foreground messages
      // through this stream instead of auto-displaying them; the correct
      // handling is to do nothing observable, not to call any repository
      // or notification method.
      final fcm = _FakeFcmClient()..token = 'initial-token';
      final repository = _FakePushRepository();
      final container = ProviderContainer(
        overrides: [
          fcmClientProvider.overrideWithValue(fcm),
          pushRepositoryProvider.overrideWithValue(repository),
        ],
      );
      addTearDown(container.dispose);
      final subscription = container.listen(
        pushDeviceRegistrationProvider,
        (_, _) {},
      );
      addTearDown(subscription.close);
      await Future<void>.delayed(Duration.zero);

      expect(
        () => fcm.emitForeground(
          const RemoteMessage(data: {'event_type': 'file_shared'}),
        ),
        returnsNormally,
      );
      await Future<void>.delayed(Duration.zero);

      expect(repository.registerCalls, [
        {'token': 'initial-token', 'platform': 'android'},
      ]);
    },
  );
}

class _FakeFcmClient implements FcmClient {
  String? token;
  final StreamController<String> _refreshController =
      StreamController.broadcast();
  final StreamController<RemoteMessage> _messageController =
      StreamController.broadcast();

  @override
  Future<String?> getToken() async => token;

  @override
  Stream<String> get onTokenRefresh => _refreshController.stream;

  @override
  Future<bool> requestPermission() async => true;

  @override
  Stream<RemoteMessage> get onMessage => _messageController.stream;

  void emitRefresh(String newToken) => _refreshController.add(newToken);

  void emitForeground(RemoteMessage message) => _messageController.add(message);
}

class _FakePushRepository implements PushRepository {
  final List<Map<String, String>> registerCalls = [];
  Object? nextRegisterError;

  @override
  ApiClient get apiClient => throw UnimplementedError();

  @override
  Future<void> registerToken({
    required String token,
    required String platform,
  }) async {
    registerCalls.add({'token': token, 'platform': platform});
    if (nextRegisterError != null) throw nextRegisterError!;
  }

  @override
  Future<void> unregisterToken(String token) async {}

  @override
  Future<void> setPushEnabled(bool enabled) async {}
}
