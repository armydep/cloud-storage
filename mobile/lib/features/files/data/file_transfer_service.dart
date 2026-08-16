import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:open_file/open_file.dart';
import 'package:path_provider/path_provider.dart';

typedef DownloadProgressCallback = void Function(double progress);

class FileTransferService {
  Future<String> download({
    required String url,
    required String fileName,
    required DownloadProgressCallback onProgress,
  }) async {
    final downloadsDirectory = await getDownloadsDirectory();
    if (downloadsDirectory == null) {
      throw Exception('Downloads directory not available');
    }

    final filePath = '${downloadsDirectory.path}/$fileName';
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
