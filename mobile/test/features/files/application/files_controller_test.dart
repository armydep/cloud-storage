import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/application/files_state.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/annotations.dart';
import 'package:mockito/mockito.dart';

import 'files_controller_test.mocks.dart';

@GenerateMocks([FilesRepository])
void main() {
  group('FilesController', () {
    late MockFilesRepository mockRepository;
    late FilesController controller;
    late Ref ref;

    setUp(() {
      mockRepository = MockFilesRepository();
      final container = ProviderContainer(
        overrides: [
          filesRepositoryProvider.overrideWithValue(mockRepository),
        ],
      );
      ref = container;
      controller = FilesController(mockRepository, ref);
    });

    test('initial state is not loading', () {
      expect(controller.state.isLoading, false);
      expect(controller.state.folder, null);
      expect(controller.state.hasError, false);
    });

    test('loadFolder sets loading state then loaded state', () async {
      final folder = FolderWithContents(
        id: '123',
        name: 'root',
        path: 'root',
        createdAt: DateTime.now(),
        contents: [],
      );

      when(mockRepository.getFolder(path: 'root'))
          .thenAnswer((_) async => folder);

      await controller.loadFolder('root');

      expect(controller.state.isLoading, false);
      expect(controller.state.folder, folder);
      expect(controller.state.hasError, false);
    });

    test('loadFolder handles FolderNotFoundError', () async {
      when(mockRepository.getFolder(path: 'nonexistent'))
          .thenThrow(FolderNotFoundError('Folder not found'));

      await controller.loadFolder('nonexistent');

      expect(controller.state.isLoading, false);
      expect(controller.state.hasError, true);
      expect(controller.state.error, 'Folder not found');
      expect(controller.state.folder, null);
    });

    test('loadFolder handles ServerError', () async {
      when(mockRepository.getFolder(path: 'root'))
          .thenThrow(ServerError('Server error'));

      await controller.loadFolder('root');

      expect(controller.state.hasError, true);
      expect(controller.state.error, 'Server error. Please try again.');
    });

    test('loadFolder handles NetworkError', () async {
      when(mockRepository.getFolder(path: 'root'))
          .thenThrow(NetworkError('Network error'));

      await controller.loadFolder('root');

      expect(controller.state.hasError, true);
      expect(controller.state.error, 'Network error. Please check your connection.');
    });

    test('navigateToFolder updates path and loads folder', () async {
      final rootFolder = FolderWithContents(
        id: '123',
        name: 'root',
        path: 'root',
        createdAt: DateTime.now(),
        contents: [],
      );

      final subfolder = FolderWithContents(
        id: '456',
        name: 'Documents',
        path: 'root.Documents',
        createdAt: DateTime.now(),
        contents: [],
      );

      when(mockRepository.getFolder(path: 'root'))
          .thenAnswer((_) async => rootFolder);
      when(mockRepository.getFolder(path: 'root.Documents'))
          .thenAnswer((_) async => subfolder);

      await controller.loadFolder('root');
      expect(controller.state.folder?.name, 'root');

      await controller.navigateToFolder('root.Documents');
      expect(controller.state.folder?.name, 'Documents');
    });

    test('navigateBack returns to parent folder', () async {
      final rootFolder = FolderWithContents(
        id: '123',
        name: 'root',
        path: 'root',
        createdAt: DateTime.now(),
        contents: [],
      );

      final subfolder = FolderWithContents(
        id: '456',
        name: 'Documents',
        path: 'root.Documents',
        createdAt: DateTime.now(),
        contents: [],
      );

      when(mockRepository.getFolder(path: anyNamed('path')))
          .thenAnswer((invocation) async {
        final path = invocation.namedArguments[#path] as String;
        if (path == 'root') return rootFolder;
        if (path == 'root.Documents') return subfolder;
        throw FolderNotFoundError('Not found');
      });

      await controller.loadFolder('root');
      await controller.navigateToFolder('root.Documents');
      await controller.navigateBack();

      expect(controller.state.folder?.name, 'root');
    });

    test('canNavigateBack returns false at root', () async {
      final folder = FolderWithContents(
        id: '123',
        name: 'root',
        path: 'root',
        createdAt: DateTime.now(),
        contents: [],
      );

      when(mockRepository.getFolder(path: 'root'))
          .thenAnswer((_) async => folder);

      await controller.loadFolder('root');

      expect(controller.canNavigateBack(), false);
    });

    test('canNavigateBack returns true in subfolder', () async {
      final rootFolder = FolderWithContents(
        id: '123',
        name: 'root',
        path: 'root',
        createdAt: DateTime.now(),
        contents: [],
      );

      final subfolder = FolderWithContents(
        id: '456',
        name: 'Documents',
        path: 'root.Documents',
        createdAt: DateTime.now(),
        contents: [],
      );

      when(mockRepository.getFolder(path: anyNamed('path')))
          .thenAnswer((invocation) async {
        final path = invocation.namedArguments[#path] as String;
        if (path == 'root') return rootFolder;
        if (path == 'root.Documents') return subfolder;
        throw FolderNotFoundError('Not found');
      });

      await controller.loadFolder('root');
      await controller.navigateToFolder('root.Documents');

      expect(controller.canNavigateBack(), true);
    });

    test('refresh reloads current folder', () async {
      final folder = FolderWithContents(
        id: '123',
        name: 'root',
        path: 'root',
        createdAt: DateTime.now(),
        contents: [],
      );

      when(mockRepository.getFolder(path: 'root'))
          .thenAnswer((_) async => folder);

      await controller.loadFolder('root');
      verify(mockRepository.getFolder(path: 'root')).called(1);

      await controller.refresh();
      verify(mockRepository.getFolder(path: 'root')).called(2);
    });
  });
}
