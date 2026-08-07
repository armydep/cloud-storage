import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';

class FilesRepository {
  final ApiClient apiClient;

  FilesRepository(this.apiClient);

  Future<FolderWithContents> getFolder({required String path}) async {
    try {
      final json = await apiClient.getJson(
        '/api/v1/files',
        authenticated: true,
        queryParameters: {'path': path},
      );

      return FolderWithContents.fromJson(json);
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        throw FolderNotFoundError('Folder not found');
      } else if (e.statusCode != null && e.statusCode! >= 500) {
        throw ServerError('Server error. Please try again.');
      } else if (e.isNetworkError) {
        throw NetworkError('Network error. Please check your connection.');
      } else {
        throw ApiError(e.message);
      }
    }
  }
}

class FolderNotFoundError implements Exception {
  final String message;
  FolderNotFoundError(this.message);

  @override
  String toString() => message;
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);

  @override
  String toString() => message;
}

class ServerError implements Exception {
  final String message;
  ServerError(this.message);

  @override
  String toString() => message;
}

class NetworkError implements Exception {
  final String message;
  NetworkError(this.message);

  @override
  String toString() => message;
}
