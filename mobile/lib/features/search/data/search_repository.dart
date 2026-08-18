import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart'
    show ApiError, NetworkError, ServerError;
import 'package:cloudestorage/features/search/domain/search_models.dart';

class SearchRepository {
  final ApiClient apiClient;

  SearchRepository(this.apiClient);

  Future<SearchPage> searchFiles({
    required String folderPath,
    String? query,
    String? category,
    int limit = 25,
    String? cursor,
  }) async {
    try {
      final json = await apiClient.getJson(
        '/api/v1/search/files',
        authenticated: true,
        queryParameters: {
          'folder_path': folderPath,
          'limit': '$limit',
          if (query != null && query.isNotEmpty) 'q': query,
          'category': ?category,
          'cursor': ?cursor,
        },
      );
      return SearchPage.fromJson(json);
    } on ApiException catch (e) {
      // A 503 means the search engine itself is unavailable (design doc
      // decision 15), and it must never be mapped the same way as a
      // genuinely empty result set, which is a normal 200 with `results: []`.
      // The existing >= 500 -> ServerError mapping already gives that
      // distinction for free -- reused here rather than duplicated.
      if (e.statusCode != null && e.statusCode! >= 500) {
        throw ServerError('Search is unavailable. Please try again later.');
      } else if (e.isNetworkError) {
        throw NetworkError(
          'Connection lost. Please check your network and try again.',
        );
      } else {
        throw ApiError(e.message);
      }
    }
  }
}
