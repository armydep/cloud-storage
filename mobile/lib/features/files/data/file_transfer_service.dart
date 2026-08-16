import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:open_file/open_file.dart';
import 'package:path_provider/path_provider.dart';

typedef DownloadProgressCallback = void Function(double progress);

class FileTransferService {
  /// Reduces a server-supplied name to a bare filename safe to join onto a
  /// directory path.
  ///
  /// The backend rejects `/` in names at upload time (`schemas.py`), but that
  /// is the only thing standing between a hostile name and the local
  /// filesystem, and it is not mirrored on the client. Strip any directory
  /// component and leading dots so a name cannot escape the destination.
  static String sanitizeFileName(String fileName) {
    final baseName = fileName.split(RegExp(r'[/\\]')).last;
    final withoutLeadingDots = baseName.replaceFirst(RegExp(r'^\.+'), '');
    return withoutLeadingDots.isEmpty ? 'download' : withoutLeadingDots;
  }

  Future<String> download({
    required String fileId,
    required String url,
    required String fileName,
    required DownloadProgressCallback onProgress,
  }) async {
    final downloadsDirectory = await getDownloadsDirectory();
    if (downloadsDirectory == null) {
      throw Exception('Downloads directory not available');
    }

    // A shared file's name is chosen by whoever shared it, not by this user.
    // Writing every download into one flat directory let a sharer pick a name
    // that truncates a file the recipient already had — and because
    // downloadedFilePaths is keyed by file id, the recipient's stale entry
    // would then open the sharer's content. Namespace by file id so names
    // from different files can never collide.
    final destinationDirectory = Directory(
      '${downloadsDirectory.path}/$fileId',
    );
    await destinationDirectory.create(recursive: true);

    final filePath =
        '${destinationDirectory.path}/${sanitizeFileName(fileName)}';
    debugPrint('Downloading $fileName to $filePath');
    await Dio().download(
      url,
      filePath,
      onReceiveProgress: (received, total) {
        if (total > 0) onProgress(received / total);
      },
    );
    debugPrint('Download completed: $filePath');
    return filePath;
  }

  Future<void> open(String filePath) async {
    final result = await OpenFile.open(filePath);
    if (result.type != ResultType.done) {
      throw Exception('Failed to open file: ${result.message}');
    }
  }
}
