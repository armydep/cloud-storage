import 'dart:async';

import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart'
    show NetworkError, ServerError;
import 'package:cloudestorage/features/search/application/search_state.dart';
import 'package:cloudestorage/features/search/data/search_repository.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final searchRepositoryProvider = Provider<SearchRepository>((ref) {
  return SearchRepository(ref.watch(apiClientProvider));
});

// Keyed by folder path: opening search from a different folder starts a
// fresh controller rather than reusing stale results, and autoDispose tears
// it down once the results screen closes.
final searchControllerProvider = StateNotifierProvider.autoDispose
    .family<FileSearchController, SearchState, String>((ref, folderPath) {
      return FileSearchController(
        ref.watch(searchRepositoryProvider),
        folderPath,
      );
    });

class FileSearchController extends StateNotifier<SearchState> {
  final SearchRepository _repository;

  static const _debounceDuration = Duration(milliseconds: 300);
  static const _pageSize = 25;

  Timer? _debounceTimer;
  // Guards against a slow, superseded request overwriting the results of a
  // request that started later -- debouncing prevents most of these races,
  // but not one where an earlier in-flight request is simply slower.
  int _requestGeneration = 0;

  FileSearchController(this._repository, String folderPath)
    : super(SearchState(folderPath: folderPath));

  @override
  void dispose() {
    _debounceTimer?.cancel();
    super.dispose();
  }

  void updateQuery(String query) {
    state = state.copyWith(query: query);
    _debounceTimer?.cancel();
    _debounceTimer = Timer(_debounceDuration, _runSearch);
  }

  Future<void> updateCategory(String? category) {
    _debounceTimer?.cancel();
    state = category == null
        ? state.copyWith(clearCategory: true)
        : state.copyWith(category: category);
    return _runSearch();
  }

  Future<void> retry() => _runSearch();

  Future<void> _runSearch() async {
    final generation = ++_requestGeneration;

    if (!state.isSearchActive) {
      state = state.copyWith(
        results: [],
        clearNextCursor: true,
        isLoading: false,
        isLoadingMore: false,
        clearError: true,
      );
      return;
    }

    state = state.copyWith(
      isLoading: true,
      isLoadingMore: false,
      clearError: true,
      results: [],
    );

    try {
      final page = await _repository.searchFiles(
        folderPath: state.folderPath,
        query: _trimmedQuery,
        category: state.category,
        limit: _pageSize,
      );
      if (!mounted || generation != _requestGeneration) return;
      state = state.copyWith(
        isLoading: false,
        results: page.results,
        nextCursor: page.nextCursor,
        clearNextCursor: page.nextCursor == null,
      );
    } on ServerError catch (e) {
      if (!mounted || generation != _requestGeneration) return;
      state = state.copyWith(isLoading: false, error: e.message);
    } on NetworkError catch (e) {
      if (!mounted || generation != _requestGeneration) return;
      state = state.copyWith(isLoading: false, error: e.message);
    } catch (e) {
      if (!mounted || generation != _requestGeneration) return;
      state = state.copyWith(
        isLoading: false,
        error: 'Search failed. Please try again.',
      );
    }
  }

  Future<void> loadMore() async {
    final cursor = state.nextCursor;
    if (cursor == null || state.isLoading || state.isLoadingMore) return;

    final generation = _requestGeneration;
    state = state.copyWith(isLoadingMore: true);

    try {
      final page = await _repository.searchFiles(
        folderPath: state.folderPath,
        query: _trimmedQuery,
        category: state.category,
        limit: _pageSize,
        cursor: cursor,
      );
      if (!mounted || generation != _requestGeneration) return;
      state = state.copyWith(
        isLoadingMore: false,
        results: [...state.results, ...page.results],
        nextCursor: page.nextCursor,
        clearNextCursor: page.nextCursor == null,
      );
    } on ServerError catch (e) {
      if (!mounted || generation != _requestGeneration) return;
      state = state.copyWith(isLoadingMore: false, error: e.message);
    } on NetworkError catch (e) {
      if (!mounted || generation != _requestGeneration) return;
      state = state.copyWith(isLoadingMore: false, error: e.message);
    } catch (e) {
      if (!mounted || generation != _requestGeneration) return;
      state = state.copyWith(
        isLoadingMore: false,
        error: 'Search failed. Please try again.',
      );
    }
  }

  String? get _trimmedQuery {
    final trimmed = state.query.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
}
