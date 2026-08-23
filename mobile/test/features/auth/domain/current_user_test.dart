import 'package:cloudestorage/features/auth/domain/current_user.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('CurrentUser.fromJson', () {
    test('defaults pushEnabled to false when absent', () {
      final user = CurrentUser.fromJson({
        'id': '1',
        'email': 'user@example.com',
        'is_active': true,
        'is_superuser': false,
      });

      expect(user.pushEnabled, false);
    });

    test('parses pushEnabled when present', () {
      final user = CurrentUser.fromJson({
        'id': '1',
        'email': 'user@example.com',
        'is_active': true,
        'is_superuser': false,
        'push_enabled': true,
      });

      expect(user.pushEnabled, true);
    });
  });
}
