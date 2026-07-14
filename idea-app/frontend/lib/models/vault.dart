/// 仓库状态
typedef VaultStatus = String; // active | fading | faded

/// 仓库统计
class VaultStats {
  final int produced;
  final int collected;
  final int forkedByOthers;

  const VaultStats({
    this.produced = 0,
    this.collected = 0,
    this.forkedByOthers = 0,
  });

  factory VaultStats.fromJson(Map<String, dynamic> json) {
    return VaultStats(
      produced: json['produced'] as int? ?? 0,
      collected: json['collected'] as int? ?? 0,
      forkedByOthers: json['forked_by_others'] as int? ?? 0,
    );
  }
}

/// 仓库圆圈
class VaultCircle {
  final String id;
  final String colorHex;
  final double sizeScore;
  final String borderStyle;
  final String status;
  final DateTime lastTouchAt;

  const VaultCircle({
    required this.id,
    required this.colorHex,
    required this.sizeScore,
    required this.borderStyle,
    required this.status,
    required this.lastTouchAt,
  });

  factory VaultCircle.fromJson(Map<String, dynamic> json) {
    return VaultCircle(
      id: json['id'] as String,
      colorHex: json['color_hex'] as String,
      sizeScore: (json['size_score'] as num).toDouble(),
      borderStyle: json['border_style'] as String? ?? 'none',
      status: json['status'] as String? ?? 'active',
      lastTouchAt: DateTime.parse(json['last_touch_at'] as String),
    );
  }
}

/// 仓库列表响应
class VaultResponse {
  final VaultStats stats;
  final List<VaultCircle> circles;
  final bool hasMore;

  const VaultResponse({
    required this.stats,
    required this.circles,
    required this.hasMore,
  });

  factory VaultResponse.fromJson(Map<String, dynamic> json) {
    return VaultResponse(
      stats: VaultStats.fromJson(
        json['stats'] as Map<String, dynamic>? ?? {},
      ),
      circles: ((json['circles'] as List<dynamic>?) ?? [])
          .map((e) => VaultCircle.fromJson(e as Map<String, dynamic>))
          .toList(),
      hasMore: json['has_more'] as bool? ?? false,
    );
  }
}

/// 收集点子响应
class CollectResponse {
  final bool collected;
  final String ideaId;

  const CollectResponse({
    required this.collected,
    required this.ideaId,
  });

  factory CollectResponse.fromJson(Map<String, dynamic> json) {
    return CollectResponse(
      collected: json['collected'] as bool? ?? true,
      ideaId: json['idea_id'] as String,
    );
  }
}

/// 移出仓库响应
class RemoveResponse {
  final bool removed;
  final String ideaId;

  const RemoveResponse({
    required this.removed,
    required this.ideaId,
  });

  factory RemoveResponse.fromJson(Map<String, dynamic> json) {
    return RemoveResponse(
      removed: json['removed'] as bool? ?? true,
      ideaId: json['idea_id'] as String,
    );
  }
}
