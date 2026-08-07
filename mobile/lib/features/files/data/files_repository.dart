import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';

class FilesRepository {
  final ApiClient apiClient;

  FilesRepository(this.apiClient);

  Future<FolderWithContents> getFolder({required String path}) async {
    try {
      final response = await apiClient.get(
        '/files',
        queryParameters: {'path': path},
      );

      if (response.statusCode == 200) {
        return FolderWithContents.fromJson(
          response.body as Map<String, dynamic>,
        );
      } else if (response.statusCode == 404) {
        throw FolderNotFoundError('Folder not found');
      } else if (response.statusCode >= 500) {
        throw ServerError('Server error: ${response.statusCode}');
      } else {
        throw ApiError('Failed to fetch folder: ${response.statusCode}');
      }
    } catch (e) {
      if (e is FolderNotFoundError || e is ServerError || e is ApiError) {
        rethrow;
      }
      throw NetworkError('Network error: $e');
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
