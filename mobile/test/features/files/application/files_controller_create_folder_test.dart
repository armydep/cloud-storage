import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FilesController.validateFolderName', () {
    test('rejects empty name', () {
      final mockRepo = _MockFilesRepository();
      final controller = FilesController(mockRepo, _MockRef());

      final error = controller.validateFolderName('');
      expect(error, 'Folder name cannot be empty');
    });

    test('rejects names longer than 255 characters', () {
      final mockRepo = _MockFilesRepository();
      final controller = FilesController(mockRepo, _MockRef());

      final longName = 'a' * 256;
      final error = controller.validateFolderName(longName);
      expect(error, contains('255'));
    });

    test('rejects invalid characters', () {
      final mockRepo = _MockFilesRepository();
      final controller = FilesController(mockRepo, _MockRef());

      final error = controller.validateFolderName('Folder\0Name');
      expect(error, isNotNull);
    });

    test('accepts valid names', () {
      final mockRepo = _MockFilesRepository();
      final controller = FilesController(mockRepo, _MockRef());

      expect(controller.validateFolderName('My Folder'), isNull);
      expect(controller.validateFolderName('my-folder'), isNull);
      expect(controller.validateFolderName('my_folder'), isNull);
      expect(controller.validateFolderName('My Folder 123'), isNull);
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
  // ignore: prefer_const_declarations
  late dynamic apiClient;
}
