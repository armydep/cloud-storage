import 'package:cloudestorage/features/files/domain/file_models.dart';

/// A single `GET /api/v1/search/files` result, matching search-svc's
/// `SearchResultItem` schema.
class SearchResultItem {
  final String id;
  final String name;
  final String folderPath;
  final String mimeType;
  final String category;
  final int sizeBytes;
  final DateTime createdAt;

  const SearchResultItem({
    required this.id,
    required this.name,
    required this.folderPath,
    required this.mimeType,
    required this.category,
    required this.sizeBytes,
    required this.createdAt,
  });

  factory SearchResultItem.fromJson(Map<String, dynamic> json) {
    return SearchResultItem(
      id: json['id'] as String,
      name: json['name'] as String,
      folderPath: json['folder_path'] as String,
      mimeType: json['mime_type'] as String,
      category: json['category'] as String,
      sizeBytes: json['size_bytes'] as int,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  /// A search result is a file. Converting it lets the results screen reuse
  /// [FileListItem], the same row presentation the folder browser uses,
  /// instead of a second one (see search_results_screen.dart).
  FileContent toFileContent() {
    return FileContent(
      id: id,
      name: name,
      type: 'file',
      sizeBytes: sizeBytes,
      category: category,
      mimeType: mimeType,
      path: folderPath,
      createdAt: createdAt,
    );
  }
}

/// One page of `GET /api/v1/search/files`. `nextCursor` is opaque -- callers
/// must pass it back unmodified and never construct or parse one.
class SearchPage {
  final List<SearchResultItem> results;
  final String? nextCursor;

  const SearchPage({required this.results, this.nextCursor});

  factory SearchPage.fromJson(Map<String, dynamic> json) {
    final data = json['results'] as List<dynamic>? ?? const [];
    return SearchPage(
      results: data
          .map(
            (item) => SearchResultItem.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );
  }
}
