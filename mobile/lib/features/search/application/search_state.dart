import 'package:cloudestorage/features/search/domain/search_models.dart';
import 'package:flutter/foundation.dart';

@immutable
class SearchState {
  final String folderPath;
  final String query;
  final String? category;
  final bool isLoading;
  final bool isLoadingMore;
  final String? error;
  final List<SearchResultItem> results;
  final String? nextCursor;

  const SearchState({
    required this.folderPath,
    this.query = '',
    this.category,
    this.isLoading = false,
    this.isLoadingMore = false,
    this.error,
    this.results = const [],
    this.nextCursor,
  });

  // A query the user hasn't finished typing yet, or no filter at all, is not
  // "no matches" -- it is not a search. The idle state and the empty-results
  // state must read differently (see search_results_screen.dart).
  bool get isSearchActive => query.trim().isNotEmpty || category != null;

  bool get hasError => error != null;
  bool get hasNextPage => nextCursor != null;
  bool get isEmpty =>
      !isLoading && !hasError && isSearchActive && results.isEmpty;

  SearchState copyWith({
    String? query,
    String? category,
    bool clearCategory = false,
    bool? isLoading,
    bool? isLoadingMore,
    String? error,
    bool clearError = false,
    List<SearchResultItem>? results,
    String? nextCursor,
    bool clearNextCursor = false,
  }) {
    return SearchState(
      folderPath: folderPath,
      query: query ?? this.query,
      category: clearCategory ? null : (category ?? this.category),
      isLoading: isLoading ?? this.isLoading,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      error: clearError ? null : (error ?? this.error),
      results: results ?? this.results,
      nextCursor: clearNextCursor ? null : (nextCursor ?? this.nextCursor),
    );
  }
}
