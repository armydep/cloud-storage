import 'package:cloudestorage/features/push/data/local_notifications_client.dart';

class FakeLocalNotificationsClient implements LocalNotificationsClient {
  final List<({int id, String title, String? body})> shown = [];
  Object? nextError;

  @override
  Future<void> show({
    required int id,
    required String title,
    String? body,
  }) async {
    if (nextError != null) throw nextError!;
    shown.add((id: id, title: title, body: body));
  }
}
