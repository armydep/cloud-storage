import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FilesController.validateFolderName', () {
    test('rejects empty name', () {
      final container = ProviderContainer(overrides: [
        filesRepositoryProvider
            .overrideWithValue(_MockFilesRepository()),
      ]);
      final controller = FilesController(
        container.read(filesRepositoryProvider),
        container,
      );

      final error = controller.validateFolderName('');
      expect(error, 'Folder name cannot be empty');
    });

    test('rejects names longer than 255 characters', () {
      final container = ProviderContainer(overrides: [
        filesRepositoryProvider
            .overrideWithValue(_MockFilesRepository()),
      ]);
      final controller = FilesController(
        container.read(filesRepositoryProvider),
        container,
      );

      final longName = 'a' * 256;
      final error = controller.validateFolderName(longName);
      expect(error, contains('255'));
    });

    test('rejects invalid characters', () {
      final container = ProviderContainer(overrides: [
        filesRepositoryProvider
            .overrideWithValue(_MockFilesRepository()),
      ]);
      final controller = FilesController(
        container.read(filesRepositoryProvider),
        container,
      );

      final error = controller.validateFolderName('Folder\0Name');
      expect(error, isNotNull);
    });

    test('accepts valid names', () {
      final container = ProviderContainer(overrides: [
        filesRepositoryProvider
            .overrideWithValue(_MockFilesRepository()),
      ]);
      final controller = FilesController(
        container.read(filesRepositoryProvider),
        container,
      );

      expect(controller.validateFolderName('My Folder'), isNull);
      expect(controller.validateFolderName('my-folder'), isNull);
      expect(controller.validateFolderName('my_folder'), isNull);
      expect(controller.validateFolderName('My Folder 123'), isNull);
    });
  });

  group('FilesController.createFolder', () {
    test('sets createError on validation failure', () async {
      final container = ProviderContainer(overrides: [
        filesRepositoryProvider
            .overrideWithValue(_MockFilesRepository()),
      ]);
      final controller = container.read(filesControllerProvider.notifier);

      await controller.createFolder('');
      expect(container.read(filesControllerProvider).createError, isNotNull);
    });

    test('calls repository and refreshes on success', () async {
      final mockRepo = _MockFilesRepository();
      final container = ProviderContainer(overrides: [
        filesRepositoryProvider.overrideWithValue(mockRepo),
      ]);
      final controller = container.read(filesControllerProvider.notifier);

      await controller.loadFolder('root');
      await controller.createFolder('New Folder');

      expect(mockRepo.createFolderCalled, true);
      expect(container.read(filesControllerProvider).isCreatingFolder, false);
      expect(container.read(filesControllerProvider).createError, isNull);
    });

    test('sets createError on duplicate name', () async {
      final mockRepo = _MockFilesRepository();
      mockRepo.shouldThrowDuplicate = true;
      final container = ProviderContainer(overrides: [
        filesRepositoryProvider.overrideWithValue(mockRepo),
      ]);
      final controller = container.read(filesControllerProvider.notifier);

      await controller.loadFolder('root');
      await controller.createFolder('Existing Folder');

      expect(container.read(filesControllerProvider).isCreatingFolder, false);
      expect(
        container.read(filesControllerProvider).createError,
        'Folder already exists',
      );
    });

    test('sets createError on server error', () async {
      final mockRepo = _MockFilesRepository();
      mockRepo.shouldThrowServer = true;
      final container = ProviderContainer(overrides: [
        filesRepositoryProvider.overrideWithValue(mockRepo),
      ]);
      final controller = container.read(filesControllerProvider.notifier);

      await controller.loadFolder('root');
      await controller.createFolder('New Folder');

      expect(container.read(filesControllerProvider).isCreatingFolder, false);
      expect(
        container.read(filesControllerProvider).createError,
        contains('error'),
      );
    });
  });
}

class _MockFilesRepository implements FilesRepository {
  bool createFolderCalled = false;
  bool shouldThrowDuplicate = false;
  bool shouldThrowServer = false;

  @override
  Future<FolderWithContents> getFolder({required String path}) async {
    return FolderWithContents(
      id: 'root-id',
      name: 'root',
      path: 'root',
      createdAt: DateTime.now(),
      contents: [],
    );
  }

  @override
  Future<FileContent> createFolder({
    required String parentPath,
    required String name,
  }) async {
    createFolderCalled = true;
    if (shouldThrowDuplicate) {
      throw DuplicateFolderNameError('Folder already exists');
    }
    if (shouldThrowServer) {
      throw ServerError('Server error');
    }
    return FileContent(
      id: 'new-folder',
      name: name,
      type: 'folder',
    );
  }

  @override
  late ApiClient apiClient;
}
