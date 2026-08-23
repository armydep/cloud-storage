import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/push/application/push_providers.dart';
import 'package:cloudestorage/features/push/data/fcm_client.dart';
import 'package:cloudestorage/features/push/data/push_repository.dart';
import 'package:cloudestorage/features/push/presentation/settings_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows the current push preference', (tester) async {
    final fcm = _FakeFcmClient();
    final repository = _FakePushRepository();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          pushControllerProvider.overrideWith(
            (ref) => PushController(repository, fcm, initiallyEnabled: true),
          ),
        ],
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );

    final switchWidget = tester.widget<SwitchListTile>(
      find.byKey(const Key('push-enabled-switch')),
    );
    expect(switchWidget.value, true);
  });

  testWidgets('turning the switch on calls enable', (tester) async {
    final fcm = _FakeFcmClient();
    final repository = _FakePushRepository();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          pushControllerProvider.overrideWith(
            (ref) => PushController(repository, fcm, initiallyEnabled: false),
          ),
        ],
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );

    await tester.tap(find.byKey(const Key('push-enabled-switch')));
    await tester.pumpAndSettle();

    expect(repository.setPushEnabledCalls, [true]);
  });

  testWidgets('turning the switch off calls disable', (tester) async {
    final fcm = _FakeFcmClient();
    final repository = _FakePushRepository();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          pushControllerProvider.overrideWith(
            (ref) => PushController(repository, fcm, initiallyEnabled: true),
          ),
        ],
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );

    await tester.tap(find.byKey(const Key('push-enabled-switch')));
    await tester.pumpAndSettle();

    expect(repository.setPushEnabledCalls, [false]);
    expect(repository.unregisterCalls, isEmpty);
  });

  testWidgets('a declined permission shows a message, switch stays off', (
    tester,
  ) async {
    final fcm = _FakeFcmClient()..permissionGranted = false;
    final repository = _FakePushRepository();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          pushControllerProvider.overrideWith(
            (ref) => PushController(repository, fcm, initiallyEnabled: false),
          ),
        ],
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );

    await tester.tap(find.byKey(const Key('push-enabled-switch')));
    await tester.pumpAndSettle();

    final switchWidget = tester.widget<SwitchListTile>(
      find.byKey(const Key('push-enabled-switch')),
    );
    expect(switchWidget.value, false);
    expect(find.textContaining('permission'), findsOneWidget);
  });
}

class _FakeFcmClient implements FcmClient {
  String? token = 'fcm-token';
  bool permissionGranted = true;

  @override
  Future<String?> getToken() async => token;

  @override
  Stream<String> get onTokenRefresh => const Stream.empty();

  @override
  Future<bool> requestPermission() async => permissionGranted;
}

class _FakePushRepository implements PushRepository {
  final List<Map<String, String>> registerCalls = [];
  final List<String> unregisterCalls = [];
  final List<bool> setPushEnabledCalls = [];

  @override
  ApiClient get apiClient => throw UnimplementedError();

  @override
  Future<void> registerToken({
    required String token,
    required String platform,
  }) async {
    registerCalls.add({'token': token, 'platform': platform});
  }

  @override
  Future<void> unregisterToken(String token) async {
    unregisterCalls.add(token);
  }

  @override
  Future<void> setPushEnabled(bool enabled) async {
    setPushEnabledCalls.add(enabled);
  }
}
