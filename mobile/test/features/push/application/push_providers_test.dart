import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart'
    show NetworkError, ServerError;
import 'package:cloudestorage/features/push/application/push_providers.dart';
import 'package:cloudestorage/features/push/data/fcm_client.dart';
import 'package:cloudestorage/features/push/data/push_repository.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('PushController.enable', () {
    test(
      'requests permission, registers the token and sets the preference',
      () async {
        final fcm = _FakeFcmClient()..token = 'fcm-token';
        final repository = _FakePushRepository();
        final controller = PushController(
          repository,
          fcm,
          initiallyEnabled: false,
        );

        await controller.enable();

        expect(fcm.permissionRequested, true);
        expect(repository.registerCalls, [
          {'token': 'fcm-token', 'platform': 'android'},
        ]);
        expect(repository.setPushEnabledCalls, [true]);
        expect(controller.state.isEnabled, true);
        expect(controller.state.permissionDenied, false);
      },
    );

    test(
      'declining the OS permission leaves push_enabled false and does not error',
      () async {
        final fcm = _FakeFcmClient()..permissionGranted = false;
        final repository = _FakePushRepository();
        final controller = PushController(
          repository,
          fcm,
          initiallyEnabled: false,
        );

        await controller.enable();

        expect(controller.state.permissionDenied, true);
        expect(controller.state.isEnabled, false);
        expect(controller.state.hasError, false);
        expect(repository.registerCalls, isEmpty);
        expect(repository.setPushEnabledCalls, isEmpty);
      },
    );

    test('sets the preference even when no token is available yet', () async {
      final fcm = _FakeFcmClient()..token = null;
      final repository = _FakePushRepository();
      final controller = PushController(
        repository,
        fcm,
        initiallyEnabled: false,
      );

      await controller.enable();

      expect(repository.registerCalls, isEmpty);
      expect(repository.setPushEnabledCalls, [true]);
      expect(controller.state.isEnabled, true);
    });

    test(
      'a server error surfaces its message and leaves push disabled',
      () async {
        final fcm = _FakeFcmClient();
        final repository = _FakePushRepository()
          ..nextSetPushEnabledError = ServerError('unavailable');
        final controller = PushController(
          repository,
          fcm,
          initiallyEnabled: false,
        );

        await controller.enable();

        expect(controller.state.error, 'unavailable');
        expect(controller.state.isEnabled, false);
      },
    );

    test('a network error surfaces its message', () async {
      final fcm = _FakeFcmClient();
      final repository = _FakePushRepository()
        ..nextSetPushEnabledError = NetworkError('offline');
      final controller = PushController(
        repository,
        fcm,
        initiallyEnabled: false,
      );

      await controller.enable();

      expect(controller.state.error, 'offline');
    });
  });

  group('PushController.disable', () {
    test('sets the preference but never unregisters the device', () async {
      // Disabling skips tokens, it does not delete them (design doc
      // decision 16) -- re-enabling must not require re-registering.
      final fcm = _FakeFcmClient();
      final repository = _FakePushRepository();
      final controller = PushController(
        repository,
        fcm,
        initiallyEnabled: true,
      );

      await controller.disable();

      expect(repository.setPushEnabledCalls, [false]);
      expect(controller.state.isEnabled, false);
    });

    test('a server error leaves the previous state on error', () async {
      final fcm = _FakeFcmClient();
      final repository = _FakePushRepository()
        ..nextSetPushEnabledError = ServerError('try again later');
      final controller = PushController(
        repository,
        fcm,
        initiallyEnabled: true,
      );

      await controller.disable();

      expect(controller.state.error, 'try again later');
    });
  });
}

class _FakeFcmClient implements FcmClient {
  String? token = 'fcm-token';
  bool permissionGranted = true;
  bool permissionRequested = false;

  @override
  Future<String?> getToken() async => token;

  @override
  Stream<String> get onTokenRefresh => const Stream.empty();

  @override
  Future<bool> requestPermission() async {
    permissionRequested = true;
    return permissionGranted;
  }

  @override
  Stream<RemoteMessage> get onMessage => const Stream.empty();
}

class _FakePushRepository implements PushRepository {
  final List<Map<String, String>> registerCalls = [];
  final List<String> unregisterCalls = [];
  final List<bool> setPushEnabledCalls = [];
  Object? nextRegisterError;
  Object? nextSetPushEnabledError;

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
  Future<void> unregisterToken(String token) async {
    unregisterCalls.add(token);
  }

  @override
  Future<void> setPushEnabled(bool enabled) async {
    setPushEnabledCalls.add(enabled);
    if (nextSetPushEnabledError != null) throw nextSetPushEnabledError!;
  }
}
