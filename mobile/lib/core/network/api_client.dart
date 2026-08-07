import 'dart:convert';

import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  const ApiException({
    required this.message,
    this.statusCode,
    this.isNetworkError = false,
  });

  final String message;
  final int? statusCode;
  final bool isNetworkError;

  bool get isAuthenticationFailure => statusCode == 401 || statusCode == 403;

  @override
  String toString() => message;
}

class ApiClient {
  factory ApiClient(
    Uri baseUri, {
    http.Client? httpClient,
    AuthSession? authSession,
  }) {
    return ApiClient._(baseUri, httpClient ?? http.Client(), authSession);
  }

  ApiClient._(this._baseUri, this._httpClient, this._authSession);

  final Uri _baseUri;
  final http.Client _httpClient;
  final AuthSession? _authSession;

  Future<Map<String, dynamic>> getJson(
    String path, {
    bool authenticated = false,
    Map<String, String>? queryParameters,
  }) async {
    final token = authenticated ? await _requiredToken() : null;
    final uri = resolve(path, queryParameters: queryParameters);
    final response = await _send(
      () => _httpClient.get(uri, headers: _headers(token: token)),
      authenticatedToken: token,
    );
    return _decodeObject(response);
  }

  Future<Map<String, dynamic>> postJson(
    String path, {
    bool authenticated = false,
    String? authenticationToken,
  }) async {
    final token =
        authenticationToken ?? (authenticated ? await _requiredToken() : null);
    final response = await _send(
      () => _httpClient.post(resolve(path), headers: _headers(token: token)),
      authenticatedToken: token,
    );
    return _decodeObject(response);
  }

  Future<Map<String, dynamic>> postForm(
    String path, {
    required Map<String, String> fields,
  }) async {
    final response = await _send(
      () => _httpClient.post(resolve(path), body: fields),
      authenticatedToken: null,
    );
    return _decodeObject(response);
  }

  Map<String, String> _headers({String? token}) {
    final headers = <String, String>{'Accept': 'application/json'};
    if (token != null) headers['Authorization'] = 'Bearer $token';
    return headers;
  }

  Future<String> _requiredToken() async {
    final token = await _authSession?.readToken();
    if (token == null || token.isEmpty) {
      throw const ApiException(
        message: 'Your session has expired. Please sign in again.',
        statusCode: 401,
      );
    }
    return token;
  }

  Future<http.Response> _send(
    Future<http.Response> Function() request, {
    required String? authenticatedToken,
  }) async {
    late http.Response response;
    try {
      response = await request();
    } on Exception {
      throw const ApiException(
        message:
            'Unable to reach the service. Check your connection and retry.',
        isNetworkError: true,
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response;
    }

    if (authenticatedToken != null &&
        (response.statusCode == 401 || response.statusCode == 403)) {
      await _authSession?.clearIfMatches(authenticatedToken);
    }

    throw ApiException(
      message: _safeErrorMessage(response),
      statusCode: response.statusCode,
    );
  }

  Map<String, dynamic> _decodeObject(http.Response response) {
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
    } on FormatException {
      // Converted to a safe response error below.
    }
    throw const ApiException(
      message: 'The service returned an invalid response.',
    );
  }

  String _safeErrorMessage(http.Response response) {
    if (response.statusCode == 400) return 'Incorrect email or password.';
    if (response.statusCode == 401 || response.statusCode == 403) {
      return 'Your session has expired. Please sign in again.';
    }
    if (response.statusCode >= 500) {
      return 'The service is temporarily unavailable. Please retry.';
    }
    return 'The request could not be completed.';
  }

  Uri resolve(String path, {Map<String, String>? queryParameters}) {
    final relativePath = path.startsWith('/') ? path.substring(1) : path;
    final uri = _baseUri.resolve(relativePath);
    if (queryParameters == null || queryParameters.isEmpty) {
      return uri;
    }
    return uri.replace(queryParameters: queryParameters);
  }

  void close() => _httpClient.close();
}
