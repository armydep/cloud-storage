class AppConfig {
  AppConfig._({required this.apiBaseUri});

  static const defaultApiBaseUrl = 'http://10.0.2.2:8000';

  final Uri apiBaseUri;

  factory AppConfig.fromEnvironment() {
    const apiBaseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: defaultApiBaseUrl,
    );

    return AppConfig.fromApiBaseUrl(apiBaseUrl);
  }

  factory AppConfig.fromApiBaseUrl(String apiBaseUrl) {
    final uri = Uri.tryParse(apiBaseUrl);
    final isHttp = uri?.scheme == 'http' || uri?.scheme == 'https';

    if (uri == null ||
        !uri.isAbsolute ||
        !isHttp ||
        uri.host.isEmpty ||
        uri.hasQuery ||
        uri.hasFragment) {
      throw FormatException(
        'API_BASE_URL must be an absolute HTTP(S) URL without a query or fragment.',
        apiBaseUrl,
      );
    }

    return AppConfig._(apiBaseUri: uri.replace(path: _normalizePath(uri.path)));
  }

  static String _normalizePath(String path) {
    if (path.isEmpty || path == '/') {
      return '/';
    }

    return path.endsWith('/') ? path : '$path/';
  }
}
