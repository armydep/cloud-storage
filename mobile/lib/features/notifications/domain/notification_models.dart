class AppNotification {
  final String id;
  final String eventType;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  final DateTime? readAt;

  const AppNotification({
    required this.id,
    required this.eventType,
    required this.payload,
    required this.createdAt,
    this.readAt,
  });

  bool get isUnread => readAt == null;

  AppNotification markedRead(DateTime at) => AppNotification(
    id: id,
    eventType: eventType,
    payload: payload,
    createdAt: createdAt,
    readAt: at,
  );

  factory AppNotification.fromJson(Map<String, dynamic> json) {
    return AppNotification(
      id: json['id'] as String,
      eventType: json['event_type'] as String,
      payload: (json['payload'] as Map<String, dynamic>?) ?? const {},
      createdAt: DateTime.parse(json['created_at'] as String),
      readAt: json['read_at'] != null
          ? DateTime.parse(json['read_at'] as String)
          : null,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AppNotification &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          readAt == other.readAt;

  @override
  int get hashCode => Object.hash(id, readAt);
}

class NotificationsPage {
  final List<AppNotification> data;
  final String? nextCursor;

  const NotificationsPage({required this.data, this.nextCursor});

  factory NotificationsPage.fromJson(Map<String, dynamic> json) {
    final items =
        (json['data'] as List<dynamic>?)
            ?.map(
              (item) => AppNotification.fromJson(item as Map<String, dynamic>),
            )
            .toList() ??
        [];

    return NotificationsPage(
      data: items,
      nextCursor: json['next_cursor'] as String?,
    );
  }
}
