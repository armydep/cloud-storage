import 'package:http/http.dart' as http;

class ApiClient {
  ApiClient(this._baseUri, {http.Client? httpClient})
    : _httpClient = httpClient ?? http.Client();

  final Uri _baseUri;
  final http.Client _httpClient;

  Future<http.Response> get(String path, {Map<String, String>? headers}) {
    return _httpClient.get(resolve(path), headers: headers);
  }

  Uri resolve(String path) {
    final relativePath = path.startsWith('/') ? path.substring(1) : path;
    return _baseUri.resolve(relativePath);
  }

  void close() => _httpClient.close();
}
