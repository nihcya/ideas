import 'dart:math' as math;

import 'package:flutter/material.dart';

/// 力导向布局节点。
///
/// 移植自 d3-force 的核心思想（velocity Verlet 积分），
/// 纯 Dart 实现，无第三方依赖。
class ForceNode {
  /// 节点唯一 key（用于命中测试和数据关联）。
  final String key;

  /// 节点显示数据（颜色 hex、作者、标题等），由调用方传入。
  final Map<String, dynamic> data;

  /// 当前位置。
  Offset position;

  /// 当前速度。
  Offset velocity;

  /// 是否固定（不参与物理模拟，如中心节点）。
  final bool fixed;

  /// 节点半径（用于 collide 力和绘制）。
  final double radius;

  ForceNode({
    required this.key,
    required this.data,
    required this.position,
    this.velocity = Offset.zero,
    this.fixed = false,
    this.radius = 20.0,
  });
}

/// 力导向布局边。
class ForceLink {
  final ForceNode source;
  final ForceNode target;

  /// 期望的连接距离（弹簧自然长度）。
  final double distance;

  ForceLink({
    required this.source,
    required this.target,
    this.distance = 80.0,
  });
}

/// 力的抽象接口。
abstract class Force {
  void apply(List<ForceNode> nodes, List<ForceLink> links, double alpha);
}

/// 节点间斥力（Charge Force）。
///
/// 所有节点两两互斥，距离越近斥力越大。
class ChargeForce extends Force {
  /// 斥力强度（正值表示互斥）。
  final double strength;

  ChargeForce({this.strength = -400.0});

  @override
  void apply(List<ForceNode> nodes, List<ForceLink> links, double alpha) {
    for (int i = 0; i < nodes.length; i++) {
      final a = nodes[i];
      if (a.fixed) continue;
      for (int j = 0; j < nodes.length; j++) {
        if (i == j) continue;
        final b = nodes[j];
        final dx = a.position.dx - b.position.dx;
        final dy = a.position.dy - b.position.dy;
        var dist2 = dx * dx + dy * dy;
        if (dist2 < 0.01) {
          // 完全重合时给个随机扰动避免除零
          dist2 = 0.01;
        }
        final dist = math.sqrt(dist2);
        // 斥力 = strength / dist2，方向从 b 指向 a
        final force = (strength * alpha) / dist2;
        a.velocity = a.velocity + Offset(
          (dx / dist) * force,
          (dy / dist) * force,
        );
      }
    }
  }
}

/// 连接弹簧力（Link Force）。
///
/// 连接的节点之间保持期望距离，过近则互斥，过远则吸引。
class LinkForce extends Force {
  /// 弹簧刚度。
  final double strength;

  LinkForce({this.strength = 0.3});

  @override
  void apply(List<ForceNode> nodes, List<ForceLink> links, double alpha) {
    for (final link in links) {
      final source = link.source;
      final target = link.target;
      final dx = target.position.dx - source.position.dx;
      final dy = target.position.dy - source.position.dy;
      var dist = math.sqrt(dx * dx + dy * dy);
      if (dist < 0.01) dist = 0.01;

      // 偏差比例：dist / link.distance，> 1 表示太远需吸引，< 1 表示太近需排斥
      final diff = (dist - link.distance) / dist;
      final force = strength * alpha * diff;

      // 沿连线方向施加力
      final fx = dx * force;
      final fy = dy * force;

      if (!source.fixed) {
        source.velocity = source.velocity + Offset(fx, fy);
      }
      if (!target.fixed) {
        target.velocity = target.velocity - Offset(fx, fy);
      }
    }
  }
}

/// 向心力（Center Force）。
///
/// 把所有节点拉向中心点，防止整体漂移。
class CenterForce extends Force {
  final Offset center;

  CenterForce({this.center = Offset.zero});

  @override
  void apply(List<ForceNode> nodes, List<ForceLink> links, double alpha) {
    double sumX = 0, sumY = 0;
    int count = 0;
    for (final n in nodes) {
      if (!n.fixed) {
        sumX += n.position.dx;
        sumY += n.position.dy;
        count++;
      }
    }
    if (count == 0) return;

    final cx = sumX / count;
    final cy = sumY / count;
    final dx = center.dx - cx;
    final dy = center.dy - cy;

    for (final n in nodes) {
      if (!n.fixed) {
        n.velocity = n.velocity + Offset(dx * alpha * 0.1, dy * alpha * 0.1);
      }
    }
  }
}

/// 碰撞力（Collide Force）。
///
/// 防止节点圆形重叠。
class CollideForce extends Force {
  CollideForce();

  @override
  void apply(List<ForceNode> nodes, List<ForceLink> links, double alpha) {
    for (int i = 0; i < nodes.length; i++) {
      final a = nodes[i];
      for (int j = i + 1; j < nodes.length; j++) {
        final b = nodes[j];
        final dx = b.position.dx - a.position.dx;
        final dy = b.position.dy - a.position.dy;
        var dist = math.sqrt(dx * dx + dy * dy);
        final minDist = a.radius + b.radius + 8; // 8pt 间隙
        if (dist < minDist && dist > 0.01) {
          final overlap = (minDist - dist) / dist;
          final push = overlap * alpha * 0.5;
          final fx = dx * push;
          final fy = dy * push;
          if (!a.fixed) {
            a.position = a.position - Offset(fx, fy);
          }
          if (!b.fixed) {
            b.position = b.position + Offset(fx, fy);
          }
        } else if (dist <= 0.01) {
          // 完全重合：随机方向推开
          final angle = (i * 37 + j * 13) % 360 * math.pi / 180.0;
          final push = (a.radius + b.radius) * alpha;
          if (!a.fixed) {
            a.position = a.position - Offset(math.cos(angle) * push, math.sin(angle) * push);
          }
          if (!b.fixed) {
            b.position = b.position + Offset(math.cos(angle) * push, math.sin(angle) * push);
          }
        }
      }
    }
  }
}

/// 力导向模拟器。
///
/// 管理 nodes/links/forces，通过 [tick] 推进一帧物理模拟。
/// alpha 从 1.0 衰减到 0，模拟"降温"过程，最终稳定。
///
/// 注意：命名为 ForceSimulation 而非 Simulation，避免与 Flutter 内置的
/// package:flutter/physics/simulation.dart 的 Simulation 类冲突。
class ForceSimulation {
  final List<ForceNode> nodes;
  final List<ForceLink> links;
  final List<Force> forces;

  /// 当前 alpha（0-1），模拟温度，每 tick 衰减。
  double _alpha = 1.0;

  /// alpha 衰减率（每 tick 乘以这个系数）。
  final double alphaDecay;

  /// alpha 低于此值认为模拟已稳定。
  final double alphaMin;

  /// 速度衰减率（模拟阻尼）。
  final double velocityDecay;

  ForceSimulation({
    required this.nodes,
    required this.links,
    required this.forces,
    this.alphaDecay = 0.0228,
    this.alphaMin = 0.001,
    this.velocityDecay = 0.4,
  });

  double get alpha => _alpha;

  bool isStable() => _alpha < alphaMin;

  /// 推进一帧模拟。
  void tick() {
    _alpha *= (1 - alphaDecay);

    // 1. 施加所有力到 velocity
    for (final force in forces) {
      force.apply(nodes, links, _alpha);
    }

    // 2. 根据 velocity 更新 position（带阻尼）
    for (final n in nodes) {
      if (n.fixed) continue;
      n.position = n.position + Offset(
        n.velocity.dx * (1 - velocityDecay),
        n.velocity.dy * (1 - velocityDecay),
      );
      // 速度归零，下一帧重新计算
      n.velocity = Offset.zero;
    }
  }

  /// 重置模拟（重新加热）。
  void reheat([double alpha = 1.0]) {
    _alpha = alpha;
  }
}
