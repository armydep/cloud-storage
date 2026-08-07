import 'package:flutter/foundation.dart';

class FileContent {
  final String id;
  final String name;
  final String type; // "file" or "folder"
  final int? sizeBytes;
  final String? category;
  final String? mimeType;
  final String? path;

  FileContent({
    required this.id,
    required this.name,
    required this.type,
    this.sizeBytes,
    this.category,
    this.mimeType,
    this.path,
  });

  bool get isFolder => type == 'folder';
  bool get isFile => type == 'file';

  String get displaySize {
    if (!isFile || sizeBytes == null) return '';
    return _formatBytes(sizeBytes!);
  }

  static String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  factory FileContent.fromJson(Map<String, dynamic> json) {
    return FileContent(
      id: json['id'] as String,
      name: json['name'] as String,
      type: json['type'] as String,
      sizeBytes: json['size_bytes'] as int?,
      category: json['category'] as String?,
      mimeType: json['mime_type'] as String?,
      path: json['path'] as String?,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FileContent &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          name == other.name &&
          type == other.type;

  @override
  int get hashCode => Object.hash(id, name, type);
}

class FolderWithContents {
  final String id;
  final String name;
  final String path;
  final DateTime createdAt;
  final List<FileContent> contents;

  FolderWithContents({
    required this.id,
    required this.name,
    required this.path,
    required this.createdAt,
    required this.contents,
  });

  List<FileContent> get folders =>
      contents.where((c) => c.isFolder).toList();

  List<FileContent> get files =>
      contents.where((c) => c.isFile).toList();

  bool get isEmpty => contents.isEmpty;

  factory FolderWithContents.fromJson(Map<String, dynamic> json) {
    print('FolderWithContents.fromJson received: $json');
    final contents = (json['contents'] as List<dynamic>?)
            ?.map((item) => FileContent.fromJson(item as Map<String, dynamic>))
            .toList() ??
        [];

    try {
      return FolderWithContents(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        path: json['path'] as String? ?? '',
        createdAt: json['created_at'] != null
            ? DateTime.parse(json['created_at'] as String)
            : DateTime.now(),
        contents: contents,
      );
    } catch (e) {
      print('Error parsing FolderWithContents: $e');
      print('JSON keys: ${json.keys}');
      rethrow;
    }
  }
}
