import 'package:cloudestorage/features/files/data/file_transfer_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  // A shared file's name is chosen by whoever shared it. The backend rejects
  // separators at upload time, but that validator is not mirrored on the
  // client, so this is the only thing keeping a hostile name from escaping the
  // destination directory.
  group('FileTransferService.sanitizeFileName', () {
    test('keeps an ordinary name unchanged', () {
      expect(FileTransferService.sanitizeFileName('report.pdf'), 'report.pdf');
    });

    test('strips posix directory components', () {
      expect(
        FileTransferService.sanitizeFileName('../../etc/passwd'),
        'passwd',
      );
    });

    test('strips windows directory components', () {
      expect(
        FileTransferService.sanitizeFileName(r'..\..\windows\system32'),
        'system32',
      );
    });

    test('strips leading dots so the name cannot traverse or hide', () {
      expect(FileTransferService.sanitizeFileName('..'), 'download');
      expect(FileTransferService.sanitizeFileName('.bashrc'), 'bashrc');
    });

    test('falls back when nothing usable remains', () {
      expect(FileTransferService.sanitizeFileName('/'), 'download');
      expect(FileTransferService.sanitizeFileName(''), 'download');
    });
  });
}
