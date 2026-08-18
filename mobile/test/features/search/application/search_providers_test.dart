import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart'
    show NetworkError, ServerError;
import 'package:cloudestorage/features/search/application/search_providers.dart';
import 'package:cloudestorage/features/search/data/search_repository.dart';
import 'package:cloudestorage/features/search/domain/search_models.dart';
import 'package:flutter_test/flutter_test.dart';

SearchResultItem _result(String id) {
  return SearchResultItem(
    id: id,
    name: '$id.pdf',
    folderPath: 'root',
    mimeType: 'application/pdf',
    category: 'document',
    sizeBytes: 1,
    createdAt: DateTime.utc(2026, 8, 17),
  );
}

void main() {
  group('FileSearchController', () {
    test('an empty query and no category is idle, not an empty search', () {
      final repository = _FakeSearchRepository();
      final controller = FileSearchController(repository, 'root');

      expect(controller.state.isSearchActive, false);
      expect(controller.state.isEmpty, false);
      expect(repository.calls, isEmpty);
    });

    test('updateCategory runs a search scoped to the given folder', () async {
      final repository = _FakeSearchRepository()
        ..responses.add(SearchPage(results: [_result('a')]));
      final controller = FileSearchController(repository, 'root.docs');

      await controller.updateCategory('document');

      expect(repository.calls.single['folderPath'], 'root.docs');
      expect(repository.calls.single['category'], 'document');
      expect(controller.state.results.map((r) => r.id), ['a']);
      expect(controller.state.isLoading, false);
    });

    test(
      'a successful empty result reads as "no matches", not an error',
      () async {
        final repository = _FakeSearchRepository()
          ..responses.add(const SearchPage(results: []));
        final controller = FileSearchController(repository, 'root');

        await controller.updateCategory('document');

        expect(controller.state.isEmpty, true);
        expect(controller.state.hasError, false);
      },
    );

    test('a 503 renders as an error, distinct from an empty result', () async {
      final repository = _FakeSearchRepository()
        ..responses.add(
          ServerError('Search is unavailable. Please try again later.'),
        );
      final controller = FileSearchController(repository, 'root');

      await controller.updateCategory('document');

      expect(controller.state.hasError, true);
      expect(controller.state.isEmpty, false);
      expect(controller.state.results, isEmpty);
      expect(
        controller.state.error,
        'Search is unavailable. Please try again later.',
      );
    });

    test('a network failure surfaces its own message', () async {
      final repository = _FakeSearchRepository()
        ..responses.add(
          NetworkError(
            'Connection lost. Please check your network and try again.',
          ),
        );
      final controller = FileSearchController(repository, 'root');

      await controller.updateCategory('document');

      expect(
        controller.state.error,
        'Connection lost. Please check your network and try again.',
      );
    });

    test(
      'loadMore appends the next page without duplicating the first',
      () async {
        final repository = _FakeSearchRepository()
          ..responses.add(
            SearchPage(
              results: [_result('a'), _result('b')],
              nextCursor: 'cursor-1',
            ),
          )
          ..responses.add(SearchPage(results: [_result('c')]));
        final controller = FileSearchController(repository, 'root');

        await controller.updateCategory('document');
        expect(controller.state.results.map((r) => r.id), ['a', 'b']);
        expect(controller.state.hasNextPage, true);

        await controller.loadMore();

        expect(controller.state.results.map((r) => r.id), ['a', 'b', 'c']);
        expect(controller.state.hasNextPage, false);
        expect(repository.calls[1]['cursor'], 'cursor-1');
      },
    );

    test('loadMore is a no-op without a next cursor', () async {
      final repository = _FakeSearchRepository()
        ..responses.add(const SearchPage(results: []));
      final controller = FileSearchController(repository, 'root');

      await controller.updateCategory('document');
      await controller.loadMore();

      expect(repository.calls.length, 1);
    });

    test('loadMore is a no-op while a page is already loading', () async {
      final repository = _FakeSearchRepository()
        ..responses.add(
          SearchPage(results: [_result('a')], nextCursor: 'cursor-1'),
        )
        ..responses.add(SearchPage(results: [_result('b')]));
      final controller = FileSearchController(repository, 'root');
      await controller.updateCategory('document');

      final first = controller.loadMore();
      final second = controller.loadMore();
      await Future.wait([first, second]);

      expect(repository.calls.length, 2); // the initial search plus one page
    });

    test(
      'a new category search replaces stale results rather than appending',
      () async {
        final repository = _FakeSearchRepository()
          ..responses.add(SearchPage(results: [_result('a')]))
          ..responses.add(SearchPage(results: [_result('b')]));
        final controller = FileSearchController(repository, 'root');

        await controller.updateCategory('document');
        await controller.updateCategory('image');

        expect(controller.state.results.map((r) => r.id), ['b']);
      },
    );

    test('clearing the category back to null returns to idle', () async {
      final repository = _FakeSearchRepository()
        ..responses.add(SearchPage(results: [_result('a')]));
      final controller = FileSearchController(repository, 'root');

      await controller.updateCategory('document');
      await controller.updateCategory(null);

      expect(controller.state.isSearchActive, false);
      expect(controller.state.results, isEmpty);
    });

    test('updateQuery debounces rapid typing into a single search', () async {
      final repository = _FakeSearchRepository()
        ..responses.add(SearchPage(results: [_result('a')]));
      final controller = FileSearchController(repository, 'root');

      controller.updateQuery('r');
      controller.updateQuery('re');
      controller.updateQuery('rep');
      controller.updateQuery('report');

      // Nothing has fired yet: typing must not issue a request per keystroke.
      expect(repository.calls, isEmpty);

      await Future<void>.delayed(const Duration(milliseconds: 350));

      expect(repository.calls.length, 1);
      expect(repository.calls.single['query'], 'report');
    });

    test(
      'a later updateQuery call cancels an earlier pending debounce',
      () async {
        final repository = _FakeSearchRepository()
          ..responses.add(SearchPage(results: [_result('a')]));
        final controller = FileSearchController(repository, 'root');

        controller.updateQuery('report');
        await Future<void>.delayed(const Duration(milliseconds: 200));
        controller.updateQuery('report final');
        await Future<void>.delayed(const Duration(milliseconds: 350));

        expect(repository.calls.length, 1);
        expect(repository.calls.single['query'], 'report final');
      },
    );

    test('retry re-issues the same search after an error', () async {
      final repository = _FakeSearchRepository()
        ..responses.add(ServerError('unavailable'))
        ..responses.add(SearchPage(results: [_result('a')]));
      final controller = FileSearchController(repository, 'root');
      await controller.updateCategory('document');
      expect(controller.state.hasError, true);

      await controller.retry();

      expect(controller.state.hasError, false);
      expect(controller.state.results.map((r) => r.id), ['a']);
    });
  });
}

class _FakeSearchRepository implements SearchRepository {
  final List<Map<String, dynamic>> calls = [];
  final List<Object> responses = [];

  @override
  ApiClient get apiClient => throw UnimplementedError();

  @override
  Future<SearchPage> searchFiles({
    required String folderPath,
    String? query,
    String? category,
    int limit = 25,
    String? cursor,
  }) async {
    calls.add({
      'folderPath': folderPath,
      'query': query,
      'category': category,
      'limit': limit,
      'cursor': cursor,
    });
    final response = responses.removeAt(0);
    if (response is Exception) {
      throw response;
    }
    return response as SearchPage;
  }
}
