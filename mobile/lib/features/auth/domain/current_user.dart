class CurrentUser {
  const CurrentUser({
    required this.id,
    required this.email,
    required this.isActive,
    required this.isSuperuser,
    this.fullName,
    this.createdAt,
    this.pushEnabled = false,
  });

  factory CurrentUser.fromJson(Map<String, dynamic> json) {
    return CurrentUser(
      id: json['id'] as String,
      email: json['email'] as String,
      isActive: json['is_active'] as bool,
      isSuperuser: json['is_superuser'] as bool,
      fullName: json['full_name'] as String?,
      createdAt: json['created_at'] == null
          ? null
          : DateTime.parse(json['created_at'] as String),
      pushEnabled: json['push_enabled'] as bool? ?? false,
    );
  }

  final String id;
  final String email;
  final bool isActive;
  final bool isSuperuser;
  final String? fullName;
  final DateTime? createdAt;
  // Opt-in (design doc decision 16): false unless the server says otherwise.
  final bool pushEnabled;
}
