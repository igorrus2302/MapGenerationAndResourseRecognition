from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from .expedition_view import WORKSPACE_PANELS, WORKSPACE_SCRIPT, WORKSPACE_STYLES, WORKSPACE_TABS
from .geophysical_observations import GEOPHYSICAL_TABLES, LEGACY_GEOPHYSICAL_TABLE, split_legacy_geophysical_bundle
from .observation_models import EXTRA_TABLE_FIELDS, prepare_preliminary_survey
from .observations import TABLE_FIELDS, with_magnetic_log_schema

HTML_TEMPLATE = r'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Геологическая разведка — карта и экспедиция</title>
  <style>
    :root {
      --ink: #25362e;
      --accent: #355d48;
      --accent-hover: #284b39;
      --highlight: #a35a35;
      --paper: #f1efe7;
      --surface: #fdfcf8;
      --surface-muted: #e9e6dc;
      --accent-tint: #e4ebe2;
      --line: #cccac0;
      --muted: #62675e;
      --text: #30382f;
      --mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
      --heading: Georgia, "Times New Roman", serif;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; }
    body {
      display: flex; flex-direction: column;
      color: var(--text); background: var(--paper);
      font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow: hidden; color-scheme: light;
    }
    header {
      flex: 0 0 auto; min-height: 62px;
      display: flex; align-items: center; justify-content: center;
      padding: 12px 26px; text-align: center;
      background: var(--surface); border-bottom: 1px solid var(--line);
    }
    header h1 { margin: 0; color: var(--ink); font: 600 22px/1.2 var(--heading); }
    .layout { flex: 1 1 0; min-height: 0; display: grid; grid-template-columns: 284px minmax(0, 1fr); }
    aside {
      min-width: 0; overflow: auto; padding: 22px 18px 26px;
      background: var(--surface); border-right: 1px solid var(--line);
    }
    .control-group { margin-bottom: 20px; padding-bottom: 17px; border-bottom: 1px solid var(--line); }
    .control-group h2 {
      margin: 0 0 11px; color: var(--ink); font-size: 11px; font-weight: 700;
      letter-spacing: .075em; text-transform: uppercase;
    }
    .map-dimensions { display: grid; grid-template-columns: auto 1fr; gap: 5px 10px; color: var(--muted); font-size: 12px; }
    .map-dimensions strong { color: var(--text); text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
    .map-seed { margin-top: 10px; padding-top: 9px; border-top: 1px solid var(--surface-muted); grid-template-columns: auto minmax(0, 1fr); }
    .map-seed strong { font: 600 11px/1.5 var(--mono); overflow-wrap: anywhere; }
    label { display: block; color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    select, button {
      width: 100%; max-width: 100%; min-width: 0; min-height: 38px;
      border: 1px solid var(--line); border-radius: 3px;
      background: var(--surface); color: var(--text); padding: 8px 11px; font: inherit;
    }
    select { cursor: pointer; }
    button { cursor: pointer; font-weight: 600; font-size: 13px; transition: background .12s, border-color .12s, color .12s; }
    button:hover:not(:disabled) { border-color: var(--accent); background: var(--accent-tint); color: var(--ink); }
    button:focus-visible, select:focus-visible, input:focus-visible, [tabindex]:focus-visible {
      outline: 2px solid var(--highlight); outline-offset: 2px;
    }
    input[type="checkbox"], input[type="range"] { accent-color: var(--accent); }
    input[type="range"] { width: 100%; }
    .button-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .range-line { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 5px; }
    .value-badge { color: var(--accent); font: 600 12px/1.4 var(--mono); text-align: right; }
    .legend-list { display: grid; }
    .legend-item {
      display: grid; grid-template-columns: 14px minmax(0, 1fr) auto; gap: 8px; align-items: center;
      padding: 7px 3px; margin: 0; border-bottom: 1px solid var(--surface-muted); color: var(--text);
      cursor: pointer; user-select: none;
    }
    .legend-item:last-child { border-bottom: 0; }
    .legend-item:hover { background: var(--paper); }
    .swatch { width: 14px; height: 14px; border: 1px solid #0002; border-radius: 1px; }
    .legend-item input { margin: 0; }
    .switch-line { display: flex; align-items: center; gap: 9px; color: var(--text); font-size: 13px; }
    .info-card {
      min-height: 100px; padding: 12px; background: var(--paper); border-left: 2px solid var(--highlight);
      color: var(--muted); font-size: 12px; overflow-wrap: anywhere;
    }
    .info-card strong { display: block; color: var(--ink); margin-bottom: 5px; font-size: 13px; }
    .info-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 3px 8px; }
    .info-grid b { color: var(--text); font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }
    main { min-width: 0; min-height: 0; padding: 20px 24px 24px; display: flex; flex-direction: column; gap: 14px; }
    .viewer-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px; }
    .viewer-toolbar h2 { margin: 0; color: var(--ink); font: 500 22px/1.2 var(--heading); }
    .canvas-shell {
      position: relative; flex: 1; min-height: 0; overflow: hidden;
      border: 1px solid var(--line); background: var(--surface);
    }
    canvas { width: 100%; height: 100%; display: block; cursor: crosshair; }
    .canvas-hint {
      position: absolute; right: 10px; bottom: 10px; max-width: min(360px, calc(100% - 20px));
      padding: 7px 10px; color: var(--muted); background: var(--surface); border: 1px solid var(--line);
      font-size: 11px; pointer-events: none;
    }
    .hidden { display: none !important; }
    @media (max-width: 860px) {
      body { height: auto; min-height: 100dvh; overflow: auto; }
      header { padding: 12px 16px; }
      .layout { flex: none; grid-template-columns: minmax(0, 1fr); }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      main { height: 70vh; min-height: 390px; padding: 16px; }
    }
    __WORKSPACE_STYLES__
  </style>
</head>
<body>
  <header>
    <h1>Геологическая разведка</h1>
  </header>

  __WORKSPACE_TABS__
  <div class="layout" id="truthPanel" role="tabpanel" aria-labelledby="tab-truth">
    <aside>
      <div class="control-group">
        <h2>Размеры карты</h2>
        <div class="map-dimensions">
          <span>Длина</span><strong id="mapLength"></strong>
          <span>Ширина</span><strong id="mapWidth"></strong>
          <span>Высота</span><strong id="mapHeight"></strong>
        </div>
        <div class="map-dimensions map-seed"><span>Seed</span><strong id="seedValue"></strong></div>
      </div>
      <div class="control-group">
        <h2>Режим просмотра</h2>
        <select id="modeSelect">
          <option value="3d">3D-блок</option>
          <option value="vertical-x">Разрез по оси X</option>
          <option value="vertical-y">Разрез по оси Y</option>
          <option value="horizontal">Разрез по оси Z</option>
        </select>
      </div>

      <div class="control-group hidden" id="depthControls">
        <h2>Координата Z</h2>
        <input id="depthSlider" type="range" min="0" step="1" value="5">
        <div class="range-line"><span id="depthLabel">Глубина Z</span><span class="value-badge" id="depthValue"></span></div>
      </div>

      <div class="control-group hidden" id="sliceControls">
        <h2>Положение разреза</h2>
        <input id="sliceSlider" type="range" min="0" step="1" value="200">
        <div class="range-line"><span id="sliceAxis">Координата</span><span class="value-badge" id="sliceValue"></span></div>
      </div>

      <div class="control-group" id="view3dControls">
        <h2>Управление 3D</h2>
        <div class="button-row">
          <button id="rotateLeft">↺ Повернуть</button>
          <button id="rotateRight">Повернуть ↻</button>
        </div>
        <button id="resetView" style="margin-top:8px">Сбросить ракурс</button>
      </div>

      <div class="control-group">
        <h2>Породы</h2>
        <div class="legend-list" id="rockLegend"></div>
      </div>

      <div class="control-group">
        <h2>Месторождения</h2>
        <label class="switch-line"><input id="depositToggle" type="checkbox" checked> Показывать минерализацию</label>
      </div>

      <div class="control-group">
        <h2>Выбранная точка</h2>
        <div class="info-card" id="cellInfo">
          <strong>Нет выбранной точки</strong>
          Нажмите на горизонтальный или вертикальный срез, чтобы увидеть данные ячейки.
        </div>
      </div>

      <button id="downloadJson">Скачать map.json</button>
    </aside>

    <main>
      <div class="viewer-toolbar">
        <h2 id="viewTitle">Трёхмерная блочная модель</h2>
      </div>
      <div class="canvas-shell" id="canvasShell">
        <canvas id="mapCanvas"></canvas>
        <div class="canvas-hint" id="canvasHint">Перетаскивайте мышью для вращения, колесом меняйте масштаб.</div>
      </div>
    </main>
  </div>

  __WORKSPACE_PANELS__
  <script>
    const MAP_DATA = __MAP_DATA__;
    const MAP_SEED_TEXT = __MAP_SEED_TEXT__;
    const OBSERVATION_DATA = __OBSERVATION_DATA__;
    const OBSERVATION_IMPORT_ROCKS = __OBSERVATION_IMPORT_ROCKS__;
    const OBSERVATION_IMPORT_XLSX = __OBSERVATION_IMPORT_XLSX__;
    const RECOGNITION_DATA = __RECOGNITION_DATA__;
    const PRELIMINARY_PLAN = __PRELIMINARY_PLAN__;
    const MANUAL_OBSERVATION_DATA = __MANUAL_OBSERVATION_DATA__;
    const PRELIMINARY_COLLECTED = __PRELIMINARY_COLLECTED__;
    const COLLECT_ENDPOINT = __COLLECT_ENDPOINT__;
    const EXPEDITION_ENDPOINT = __EXPEDITION_ENDPOINT__;
    const EXPEDITION_COLLECTED = __EXPEDITION_COLLECTED__;

    const canvas = document.getElementById('mapCanvas');
    const ctx = canvas.getContext('2d');
    const shell = document.getElementById('canvasShell');
    const modeSelect = document.getElementById('modeSelect');
    const depthSlider = document.getElementById('depthSlider');
    const depthValue = document.getElementById('depthValue');
    const sliceSlider = document.getElementById('sliceSlider');
    const sliceValue = document.getElementById('sliceValue');
    const sliceAxis = document.getElementById('sliceAxis');
    const depositToggle = document.getElementById('depositToggle');
    const viewTitle = document.getElementById('viewTitle');
    const canvasHint = document.getElementById('canvasHint');
    const cellInfo = document.getElementById('cellInfo');
    const dims = MAP_DATA.dimensions;
    const rockById = Object.fromEntries(MAP_DATA.rocks.map(rock => [rock.id, rock]));
    const depositById = Object.fromEntries(MAP_DATA.deposits.map(deposit => [deposit.id, deposit]));
    const cells = MAP_DATA.cells;
    const terrain = MAP_DATA.terrain;
    const geophysicalChannels = {
      magnetic: {field: 'magnetic_anomaly_nt', label: 'Магнитная аномалия', unit: 'нТл'},
      gamma: {field: 'gamma_count_rate_cps', label: 'Гамма-фон', unit: 'имп/с'}
    };
    const highestDepth = terrain ? Math.floor(-terrain.max_elevation_m) : 0;
    const VIEW_STEP_M = 1;
    const presentRockIds = new Set(
      cells.flatMap(cell => cell.intervals.map(interval => interval.rock_id))
    );
    const presentRocks = MAP_DATA.rocks.filter(rock => presentRockIds.has(rock.id));

    const state = {
      mode: '3d',
      depthM: Math.max(highestDepth, Math.min(5, dims.depth_m - 1)),
      slicePositionM: Math.floor(dims.width_m / 2),
      angle: -Math.PI / 4,
      zoom: 1,
      showDeposit: true,
      visibleRocks: new Set(presentRocks.map(rock => rock.id)),
      hitMap: null,
      dragging: false,
      dragX: 0
    };

    document.getElementById('seedValue').textContent = MAP_SEED_TEXT;
    document.getElementById('mapLength').textContent = `${dims.height_m} м`;
    document.getElementById('mapWidth').textContent = `${dims.width_m} м`;
    document.getElementById('mapHeight').textContent = `${dims.depth_m} м`;

    function cellAt(x, y) {
      if (x < 0 || y < 0 || x >= dims.width_cells || y >= dims.height_cells) return null;
      return cells[y * dims.width_cells + x];
    }

    function intervalAt(cell, depthM) {
      if (!cell) return null;
      return cell.intervals.find(interval => depthM >= interval.from_depth_m && depthM < interval.to_depth_m)
        || null;
    }

    function elevationAt(x, y, fallback) {
      return cellAt(x, y)?.surface_elevation_m ?? fallback;
    }

    function mineralizationAt(cell, depthM) {
      if (!cell) return null;
      const matches = cell.mineralization.filter(
        item => depthM >= item.from_depth_m && depthM < item.to_depth_m
      );
      return matches.reduce(
        (best, item) => !best || depositStrength(item) > depositStrength(best)
          ? item : best,
        null
      );
    }

    function depositFor(item) {
      return item ? depositById[item.deposit_id] : null;
    }

    function depositStrength(item) {
      const deposit = depositFor(item);
      return deposit ? Math.min(1, item.maximum_grade / deposit.max_grade) : 0;
    }

    function formatGrade(value) {
      if (value < 0.01) return value.toFixed(4);
      if (value < 1) return value.toFixed(3);
      return value.toFixed(2);
    }

    function controlName(control) {
      return ({
        host: 'порода-хозяин',
        stratiform: 'пластовый',
        contact: 'контакт пород',
        fault: 'разлом',
        intrusive: 'интрузивное тело'
      })[control] || control;
    }

    function hexToRgb(hex) {
      const value = hex.replace('#', '');
      return {
        r: parseInt(value.slice(0, 2), 16),
        g: parseInt(value.slice(2, 4), 16),
        b: parseInt(value.slice(4, 6), 16)
      };
    }

    function rgba(hex, alpha = 1, factor = 1) {
      const {r, g, b} = hexToRgb(hex);
      const clamp = value => Math.max(0, Math.min(255, Math.round(value * factor)));
      return `rgba(${clamp(r)},${clamp(g)},${clamp(b)},${alpha})`;
    }

    function resizeCanvas() {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const rect = shell.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      canvas.width = Math.max(1, Math.round(rect.width * ratio));
      canvas.height = Math.max(1, Math.round(rect.height * ratio));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      requestRender();
    }

    function canvasSize() {
      return { width: canvas.clientWidth, height: canvas.clientHeight };
    }

    let renderRequested = false;
    function requestRender() {
      if (renderRequested) return;
      renderRequested = true;
      requestAnimationFrame(() => {
        renderRequested = false;
        render();
      });
    }

    function clearCanvas() {
      const {width, height} = canvasSize();
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#faf9f4';
      ctx.fillRect(0, 0, width, height);
    }

    function render() {
      if (document.getElementById('truthPanel').classList.contains('hidden')) return;
      clearCanvas();
      if (state.mode === '3d') render3D();
      else if (state.mode === 'horizontal') renderHorizontal();
      else renderVertical(state.mode === 'vertical-x' ? 'x' : 'y');
    }

    function drawPolygon(points, fill, stroke = null, width = 0.45) {
      if (!points.length) return;
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let index = 1; index < points.length; index++) ctx.lineTo(points[index].x, points[index].y);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = width;
        ctx.stroke();
      }
    }

    function projectionFor3D(width, height) {
      const centerX = dims.width_cells / 2;
      const centerY = dims.height_cells / 2;
      const depthSteps = dims.depth_m / dims.depth_step_m;
      const cos = Math.cos(state.angle);
      const sin = Math.sin(state.angle);
      function raw(x, y, z) {
        const dx = x - centerX;
        const dy = y - centerY;
        const rx = dx * cos - dy * sin;
        const ry = dx * sin + dy * cos;
        return {x: rx, y: ry * 0.46 + z * 0.72, depth: ry + z * 0.025};
      }
      const corners = [];
      for (const x of [0, dims.width_cells]) {
        for (const y of [0, dims.height_cells]) {
          for (const z of [highestDepth / dims.depth_step_m, depthSteps]) corners.push(raw(x, y, z));
        }
      }
      const minX = Math.min(...corners.map(point => point.x));
      const maxX = Math.max(...corners.map(point => point.x));
      const minY = Math.min(...corners.map(point => point.y));
      const maxY = Math.max(...corners.map(point => point.y));
      const scale = Math.min((width - 70) / (maxX - minX), (height - 80) / (maxY - minY)) * state.zoom;
      const offsetX = width / 2 - ((minX + maxX) / 2) * scale;
      const offsetY = height / 2 - ((minY + maxY) / 2) * scale;
      return {
        raw,
        point(x, y, z) {
          const projected = raw(x, y, z);
          return {x: offsetX + projected.x * scale, y: offsetY + projected.y * scale, depth: projected.depth};
        },
        sin,
        cos
      };
    }

    function render3D() {
      const {width, height} = canvasSize();
      const projection = projectionFor3D(width, height);
      const baseShapes = [];

      for (let y = 0; y < dims.height_cells; y++) {
        for (let x = 0; x < dims.width_cells; x++) {
          const cell = cellAt(x, y);
          const rock = rockById[cell.intervals[0].rock_id];
          if (!state.visibleRocks.has(rock.id)) continue;
          const elevation = cell.surface_elevation_m ?? 0;
          const z = -elevation / dims.depth_step_m;
          const shade = surfaceShade(cell);
          const points = [
            projection.point(x, y, z), projection.point(x + 1, y, z),
            projection.point(x + 1, y + 1, z), projection.point(x, y + 1, z)
          ];
          baseShapes.push({
            points,
            depth: points.reduce((sum, point) => sum + point.depth, 0) / points.length,
            fill: rgba(rock.color, 1, shade),
            stroke: 'rgba(39,49,39,.11)'
          });
          const stepX = projection.sin >= 0 ? 1 : -1, stepY = projection.cos >= 0 ? 1 : -1;
          for (const [otherX, otherY, a, b] of [
            [x + stepX, y, [x + (stepX > 0 ? 1 : 0), y], [x + (stepX > 0 ? 1 : 0), y + 1]],
            [x, y + stepY, [x, y + (stepY > 0 ? 1 : 0)], [x + 1, y + (stepY > 0 ? 1 : 0)]]
          ]) {
            const lower = elevationAt(otherX, otherY, elevation);
            if (lower >= elevation) continue;
            const bottom = -lower / dims.depth_step_m;
            const edge = [projection.point(...a, z), projection.point(...b, z), projection.point(...b, bottom), projection.point(...a, bottom)];
            baseShapes.push({points: edge, depth: edge.reduce((sum, point) => sum + point.depth, 0) / edge.length,
                             fill: rgba(rock.color, 1, shade * .72), stroke: null});
          }
        }
      }

      const nearX = projection.sin >= 0 ? dims.width_cells : 0;
      const cellX = nearX === 0 ? 0 : dims.width_cells - 1;
      for (let y = 0; y < dims.height_cells; y++) {
        const cell = cellAt(cellX, y);
        for (const interval of cell.intervals) {
          if (!state.visibleRocks.has(interval.rock_id)) continue;
          const rock = rockById[interval.rock_id];
          const z1 = interval.from_depth_m / dims.depth_step_m;
          const z2 = interval.to_depth_m / dims.depth_step_m;
          const points = [
            projection.point(nearX, y, z1), projection.point(nearX, y + 1, z1),
            projection.point(nearX, y + 1, z2), projection.point(nearX, y, z2)
          ];
          baseShapes.push({
            points,
            depth: points.reduce((sum, point) => sum + point.depth, 0) / points.length,
            fill: rgba(rock.color, 1, 0.84),
            stroke: 'rgba(39,49,39,.13)'
          });
        }
      }

      const nearY = projection.cos >= 0 ? dims.height_cells : 0;
      const cellY = nearY === 0 ? 0 : dims.height_cells - 1;
      for (let x = 0; x < dims.width_cells; x++) {
        const cell = cellAt(x, cellY);
        for (const interval of cell.intervals) {
          if (!state.visibleRocks.has(interval.rock_id)) continue;
          const rock = rockById[interval.rock_id];
          const z1 = interval.from_depth_m / dims.depth_step_m;
          const z2 = interval.to_depth_m / dims.depth_step_m;
          const points = [
            projection.point(x, nearY, z1), projection.point(x + 1, nearY, z1),
            projection.point(x + 1, nearY, z2), projection.point(x, nearY, z2)
          ];
          baseShapes.push({
            points,
            depth: points.reduce((sum, point) => sum + point.depth, 0) / points.length,
            fill: rgba(rock.color, 1, 0.72),
            stroke: 'rgba(39,49,39,.14)'
          });
        }
      }

      baseShapes.sort((a, b) => a.depth - b.depth);
      for (const shape of baseShapes) drawPolygon(shape.points, shape.fill, shape.stroke);

      if (state.showDeposit) {
        const depositShapes = [];
        for (const cell of cells) {
          if (!cell.mineralization.length) continue;
          for (const item of cell.mineralization) {
            const deposit = depositFor(item);
            const x = cell.x_index;
            const y = cell.y_index;
            const z1 = item.from_depth_m / dims.depth_step_m;
            const z2 = item.to_depth_m / dims.depth_step_m;
            const xFace = projection.sin >= 0 ? x + 1 : x;
            const yFace = projection.cos >= 0 ? y + 1 : y;
            const alpha = 0.30 + 0.34 * depositStrength(item);
            const fill = rgba(deposit.color, alpha, 1.08);
            const top = [
              projection.point(x, y, z1), projection.point(x + 1, y, z1),
              projection.point(x + 1, y + 1, z1), projection.point(x, y + 1, z1)
            ];
            const sideX = [
              projection.point(xFace, y, z1), projection.point(xFace, y + 1, z1),
              projection.point(xFace, y + 1, z2), projection.point(xFace, y, z2)
            ];
            const sideY = [
              projection.point(x, yFace, z1), projection.point(x + 1, yFace, z1),
              projection.point(x + 1, yFace, z2), projection.point(x, yFace, z2)
            ];
            for (const points of [top, sideX, sideY]) {
              depositShapes.push({
                points,
                depth: points.reduce((sum, point) => sum + point.depth, 0) / points.length,
                fill
              });
            }
          }
        }
        depositShapes.sort((a, b) => a.depth - b.depth);
        for (const shape of depositShapes) {
          drawPolygon(shape.points, shape.fill, 'rgba(146,45,15,.22)', 0.5);
        }
      }

      state.hitMap = null;
    }

    function gridGeometry(columns, rows, horizontalStepM = VIEW_STEP_M) {
      const {width, height} = canvasSize();
      const padding = {left: 52, right: 24, top: 42, bottom: 48};
      const cellSize = Math.min(
        (width - padding.left - padding.right) / columns,
        (height - padding.top - padding.bottom) / rows
      );
      const gridWidth = cellSize * columns;
      const gridHeight = cellSize * rows;
      const left = padding.left + Math.max(0, (width - padding.left - padding.right - gridWidth) / 2);
      const top = padding.top + Math.max(0, (height - padding.top - padding.bottom - gridHeight) / 2);
      return {left, top, cellSize, gridWidth, gridHeight, columns, rows, horizontalStepM};
    }

    function renderHorizontal() {
      const depthM = state.depthM;
      const geometry = gridGeometry(dims.width_m, dims.height_m);
      const sourceCellSize = geometry.cellSize * dims.cell_size_m;
      for (let y = 0; y < dims.height_cells; y++) {
        for (let x = 0; x < dims.width_cells; x++) {
          const cell = cellAt(x, y);
          const interval = intervalAt(cell, depthM);
          if (!interval) continue;
          const rock = rockById[interval.rock_id];
          const sx = geometry.left + cell.x_m * geometry.cellSize;
          const sy = geometry.top + cell.y_m * geometry.cellSize;
          ctx.fillStyle = state.visibleRocks.has(rock.id) ? rock.color : '#e5e3db';
          ctx.fillRect(sx, sy, sourceCellSize + .3, sourceCellSize + .3);
          const mineral = state.showDeposit ? mineralizationAt(cell, depthM) : null;
          if (mineral) {
            const alpha = 0.25 + 0.65 * depositStrength(mineral);
            ctx.fillStyle = rgba(depositFor(mineral).color, alpha);
            ctx.fillRect(sx, sy, sourceCellSize + .3, sourceCellSize + .3);
          }
        }
      }
      drawGridFrame(geometry, terrain ? `Разрез по оси Z · отметка ${-depthM} м` : `Разрез по оси Z: глубина ${Math.round(depthM)} м`);
      state.hitMap = {type: 'horizontal', geometry, depthM};
    }

    function surfaceShade(cell) {
      const {x_index: x, y_index: y, surface_elevation_m: elevation = 0} = cell;
      const dx = elevationAt(x + 1, y, elevation) - elevationAt(x - 1, y, elevation);
      const dy = elevationAt(x, y + 1, elevation) - elevationAt(x, y - 1, elevation);
      return Math.max(.68, Math.min(1.28, 1.05 + (dx + dy) / (4 * dims.cell_size_m)));
    }

    function geophysicalColor(fraction) {
      return `hsl(${232 - 212 * fraction}, 67%, ${42 + 11 * fraction}%)`;
    }

    function renderVertical(axis) {
      const columns = axis === 'x' ? dims.height_m : dims.width_m;
      const sourceColumns = axis === 'x' ? dims.height_cells : dims.width_cells;
      const maximumIndex = axis === 'x' ? dims.width_cells - 1 : dims.height_cells - 1;
      const sliceIndex = Math.min(
        maximumIndex,
        Math.floor(state.slicePositionM / dims.cell_size_m)
      );
      const geometry = gridGeometry(columns, dims.depth_m - highestDepth);
      const sourceWidth = geometry.cellSize * dims.cell_size_m;
      for (let horizontal = 0; horizontal < sourceColumns; horizontal++) {
        const x = axis === 'x' ? sliceIndex : horizontal;
        const y = axis === 'x' ? horizontal : sliceIndex;
        const cell = cellAt(x, y);
        const sx = geometry.left + horizontal * dims.cell_size_m * geometry.cellSize;
        for (const interval of cell.intervals) {
          const rock = rockById[interval.rock_id];
          const sy = geometry.top + (interval.from_depth_m - highestDepth) * geometry.cellSize;
          const intervalHeight = (
            interval.to_depth_m - interval.from_depth_m
          ) * geometry.cellSize;
          ctx.fillStyle = state.visibleRocks.has(rock.id) ? rock.color : '#e5e3db';
          ctx.fillRect(sx, sy, sourceWidth + .3, intervalHeight + .3);
        }
        if (state.showDeposit) {
          for (const mineral of cell.mineralization) {
            const sy = geometry.top + (mineral.from_depth_m - highestDepth) * geometry.cellSize;
            const mineralHeight = (
              mineral.to_depth_m - mineral.from_depth_m
            ) * geometry.cellSize;
            const alpha = 0.25 + 0.65 * depositStrength(mineral);
            ctx.fillStyle = rgba(depositFor(mineral).color, alpha);
            ctx.fillRect(sx, sy, sourceWidth + .3, Math.max(.3, mineralHeight));
          }
        }
      }
      const coordinate = state.slicePositionM;
      drawGridFrame({...geometry, elevationAxis: Boolean(terrain)}, `Вертикальный разрез: ${axis.toUpperCase()} = ${coordinate} м`);
      state.hitMap = {type: `vertical-${axis}`, geometry, axis, sliceIndex};
    }

    function drawGridFrame(geometry, title) {
      function gridLine(vertical, positionM, strong) {
        const position = vertical
          ? geometry.left + positionM * geometry.cellSize
          : geometry.top + positionM * geometry.cellSize;
        const startX = vertical ? position : geometry.left;
        const startY = vertical ? geometry.top : position;
        const endX = vertical ? position : geometry.left + geometry.gridWidth;
        const endY = vertical ? geometry.top + geometry.gridHeight : position;

        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = strong ? 'rgba(255,255,255,.62)' : 'rgba(255,255,255,.38)';
        ctx.lineWidth = strong ? 2.2 : 1.4;
        ctx.stroke();
        ctx.strokeStyle = strong ? 'rgba(37,54,46,.62)' : 'rgba(37,54,46,.32)';
        ctx.lineWidth = strong ? 1.15 : .65;
        ctx.stroke();
      }

      for (let x = 10; x < geometry.columns; x += 10) {
        gridLine(true, x, x % 50 === 0);
      }
      for (let y = 10; y < geometry.rows; y += 10) {
        gridLine(false, y, y % 50 === 0);
      }

      ctx.strokeStyle = 'rgba(37,54,46,.72)';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(geometry.left, geometry.top, geometry.gridWidth, geometry.gridHeight);
      ctx.fillStyle = '#25362e';
      ctx.font = '600 13px system-ui, sans-serif';
      ctx.fillText(title, geometry.left, geometry.top - 15);
      ctx.fillStyle = '#62675e';
      ctx.font = '11px system-ui, sans-serif';
      ctx.fillText('0 м', geometry.left - 2, geometry.top + geometry.gridHeight + 22);
      const labelStep = geometry.cellSize * 50 >= 42 ? 50 : 100;
      ctx.textAlign = 'center';
      for (let x = labelStep; x < geometry.columns; x += labelStep) {
        ctx.fillText(
          `${x} м`,
          geometry.left + x * geometry.cellSize,
          geometry.top + geometry.gridHeight + 22
        );
      }
      ctx.textAlign = 'right';
      ctx.fillText(`${geometry.columns * geometry.horizontalStepM} м`, geometry.left + geometry.gridWidth, geometry.top + geometry.gridHeight + 22);
      ctx.textBaseline = 'middle';
      for (let y = labelStep; y < geometry.rows; y += labelStep) {
        ctx.fillText(
          `${geometry.invertY ? geometry.rows - y : geometry.elevationAxis ? -highestDepth - y : y} м`,
          geometry.left - 8,
          geometry.top + y * geometry.cellSize
        );
      }
      ctx.textBaseline = 'alphabetic';
      ctx.textAlign = 'left';
    }

    function updateControls() {
      const is3D = state.mode === '3d';
      const isHorizontal = state.mode === 'horizontal';
      const isVertical = state.mode.startsWith('vertical');
      document.getElementById('view3dControls').classList.toggle('hidden', !is3D);
      document.getElementById('depthControls').classList.toggle('hidden', !isHorizontal);
      document.getElementById('sliceControls').classList.toggle('hidden', !isVertical);
      depthSlider.min = String(highestDepth);
      depthSlider.max = String(dims.depth_m - 1);
      depthSlider.value = String(state.depthM);
      document.getElementById('depthLabel').textContent = terrain ? 'Отметка Z' : 'Глубина Z';
      depthValue.textContent = `${terrain ? -state.depthM : state.depthM} м`;
      if (isVertical) {
        const axis = state.mode === 'vertical-x' ? 'X' : 'Y';
        const maximum = (axis === 'X' ? dims.width_m : dims.height_m) - 1;
        state.slicePositionM = Math.min(state.slicePositionM, maximum);
        sliceSlider.max = String(maximum);
        sliceSlider.value = String(state.slicePositionM);
        sliceAxis.textContent = `Координата ${axis}`;
        sliceValue.textContent = `${state.slicePositionM} м`;
      }
      const titles = {
        '3d': 'Трёхмерная блочная модель',
        'horizontal': 'Разрез по оси Z — плоскость X–Y',
        'vertical-x': 'Разрез по оси X — плоскость Y–Z',
        'vertical-y': 'Разрез по оси Y — плоскость X–Z'
      };
      viewTitle.textContent = titles[state.mode];
      canvasHint.textContent = is3D
        ? 'Перетаскивайте мышью для вращения, колесом меняйте масштаб.'
        : 'Выбор — 1 м; линии сетки — 10 м, усиленные линии — 50 м.';
      canvas.style.cursor = is3D ? 'grab' : 'crosshair';
      requestRender();
    }

    function showCellInfo(cell, depthM, pointX, pointY) {
      const interval = intervalAt(cell, depthM);
      const elevation = cell.surface_elevation_m ?? 0;
      if (!interval) {
        cellInfo.textContent = `Точка выше поверхности. Отметка земли ${elevation} м.`;
        return;
      }
      const rock = rockById[interval.rock_id];
      const mineral = mineralizationAt(cell, depthM);
      const deposit = depositFor(mineral);
      const title = mineral ? deposit.name : rock.name;
      const hostRock = mineral ? (rockById[mineral.host_rock_id] || rock) : rock;
      const mineralRows = mineral
        ? `
          <span>Ископаемое</span><b>${mineral.mineral}</b>
          <span>Содержание</span><b>${formatGrade(mineral.average_grade)} ${mineral.grade_unit}</b>
          <span>Порода-носитель</span><b>${hostRock.name}</b>
          <span>Геологический контроль</span><b>${controlName(mineral.geological_control)}</b>`
        : `
          <span>Ископаемое</span><b>нет</b>
          <span>Порода</span><b>${rock.name}</b>`;
      cellInfo.innerHTML = `
        <strong>${title}</strong>
        <div class="info-grid">
          <span>Точка 1 × 1 м</span><b>X ${pointX}-${Math.min(pointX + VIEW_STEP_M, dims.width_m)} / Y ${pointY}-${Math.min(pointY + VIEW_STEP_M, dims.height_m)} м</b>
          <span>Исходная ячейка</span><b>(${cell.x_index}, ${cell.y_index}), ${dims.cell_size_m} × ${dims.cell_size_m} м</b>
          ${terrain ? `<span>Отметка поверхности</span><b>${elevation} м</b><span>Отметка Z</span><b>${Math.round(-depthM * 1000) / 1000} м</b>` : ''}
          <span>Глубина от поверхности</span><b>${Math.round((depthM + elevation) * 1000) / 1000} м</b>
          <span>Интервал от поверхности</span><b>${Math.round((interval.from_depth_m + elevation) * 1000) / 1000}–${Math.round((interval.to_depth_m + elevation) * 1000) / 1000} м</b>
          ${mineralRows}
          <span>Плотность</span><b>${interval.properties.density_g_cm3} г/см³</b>
          <span>Пористость</span><b>${interval.properties.porosity_percent} %</b>
        </div>`;
    }

    function hitTest(event) {
      if (!state.hitMap) return;
      const rect = canvas.getBoundingClientRect();
      const mouseX = event.clientX - rect.left;
      const mouseY = event.clientY - rect.top;
      const {geometry} = state.hitMap;
      const column = Math.floor((mouseX - geometry.left) / geometry.cellSize);
      const row = Math.floor((mouseY - geometry.top) / geometry.cellSize);
      if (column < 0 || row < 0 || column >= geometry.columns || row >= geometry.rows) return;
      if (state.hitMap.type === 'horizontal') {
        const cell = cellAt(
          Math.floor(column / dims.cell_size_m),
          Math.floor(row / dims.cell_size_m)
        );
        showCellInfo(cell, state.hitMap.depthM, column, row);
        return;
      }
      const depthM = highestDepth + row;
      const horizontalIndex = Math.floor(column / dims.cell_size_m);
      const cell = state.hitMap.axis === 'x'
        ? cellAt(state.hitMap.sliceIndex, horizontalIndex)
        : cellAt(horizontalIndex, state.hitMap.sliceIndex);
      const pointX = state.hitMap.axis === 'x' ? state.slicePositionM : column;
      const pointY = state.hitMap.axis === 'x' ? column : state.slicePositionM;
      showCellInfo(cell, depthM, pointX, pointY);
    }

    function buildLegend() {
      const legend = document.getElementById('rockLegend');
      legend.innerHTML = '';
      for (const rock of presentRocks) {
        const item = document.createElement('label');
        item.className = 'legend-item';
        item.innerHTML = `<span class="swatch" style="background:${rock.color}"></span><span>${rock.name}</span><input type="checkbox" checked>`;
        const input = item.querySelector('input');
        input.addEventListener('change', () => {
          if (input.checked) state.visibleRocks.add(rock.id);
          else state.visibleRocks.delete(rock.id);
          requestRender();
        });
        legend.appendChild(item);
      }
    }

    modeSelect.addEventListener('change', () => {
      state.mode = modeSelect.value;
      state.hitMap = null;
      updateControls();
    });
    depthSlider.addEventListener('input', () => {
      state.depthM = Number(depthSlider.value);
      updateControls();
    });
    sliceSlider.addEventListener('input', () => {
      state.slicePositionM = Number(sliceSlider.value);
      updateControls();
    });
    depositToggle.addEventListener('change', () => {
      state.showDeposit = depositToggle.checked;
      requestRender();
    });
    document.getElementById('rotateLeft').addEventListener('click', () => {
      state.angle -= Math.PI / 8;
      requestRender();
    });
    document.getElementById('rotateRight').addEventListener('click', () => {
      state.angle += Math.PI / 8;
      requestRender();
    });
    document.getElementById('resetView').addEventListener('click', () => {
      state.angle = -Math.PI / 4;
      state.zoom = 1;
      requestRender();
    });
    document.getElementById('downloadJson').addEventListener('click', () => {
      const blob = new Blob([JSON.stringify(MAP_DATA, null, 2)], {type: 'application/json'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'map.json';
      link.click();
      URL.revokeObjectURL(url);
    });

    canvas.addEventListener('click', event => {
      if (state.mode !== '3d') hitTest(event);
    });
    canvas.addEventListener('pointerdown', event => {
      if (state.mode !== '3d') return;
      state.dragging = true;
      state.dragX = event.clientX;
      canvas.setPointerCapture(event.pointerId);
      canvas.style.cursor = 'grabbing';
    });
    canvas.addEventListener('pointermove', event => {
      if (!state.dragging || state.mode !== '3d') return;
      state.angle += (event.clientX - state.dragX) * 0.012;
      state.dragX = event.clientX;
      requestRender();
    });
    canvas.addEventListener('pointerup', event => {
      if (!state.dragging) return;
      state.dragging = false;
      canvas.releasePointerCapture(event.pointerId);
      canvas.style.cursor = 'grab';
    });
    canvas.addEventListener('wheel', event => {
      if (state.mode !== '3d') return;
      event.preventDefault();
      state.zoom = Math.max(.55, Math.min(1.8, state.zoom * (event.deltaY > 0 ? .92 : 1.08)));
      requestRender();
    }, {passive: false});

    buildLegend();
    new ResizeObserver(resizeCanvas).observe(shell);
    updateControls();
    __WORKSPACE_SCRIPT__
  </script>
</body>
</html>
'''


def _manual_observation_bundle(data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Empty import workspace: schema and expedition settings, no observations."""
    dims = data["dimensions"]
    return {
        "schema_version": "1.9", "data_kind": "exploration_observations",
        "campaign": {**{key: config[key] for key in ("campaign_id", "title", "date")},
                     "coordinate_system": "local_cartesian",
                     "width_m": dims["width_m"], "height_m": dims["height_m"]},
        "plan": {"layout": config["drilling"].get("layout", "grid"),
                 "sample_length_m": config["drilling"]["sample_length_m"],
                 "borehole_path": "straight", "borehole_depth_reference": "measured_depth_m",
                 "ideal": config.get("ideal", False), "analytes": config["analytes"],
                 "methods": {name: config.get(name, {}) for name in
                             ("geophysical_survey", "terrain_survey", "outcrops", "surface_geochemistry")}},
        "tables": {name: [] for name in TABLE_FIELDS}, "table_fields": TABLE_FIELDS,
        "summary": {}, "rock_catalog": [], "geojson": {}, "borehole_sources": [], "notes": [],
    }


def build_viewer(data: dict[str, Any], path: str | Path, *, observations: dict[str, Any] | None = None,
                 recognition: dict[str, Any] | None = None, observation_config: dict[str, Any] | None = None,
                 observation_seed: int | None = None, collect_endpoint: str | None = None,
                 preliminary_collected: bool = False, expedition_endpoint: str | None = None,
                 expedition_collected: bool | None = None) -> Path:
    """Create an offline workspace for truth, surveys, fieldwork, recognition and comparison."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    legacy_survey = observations is not None and LEGACY_GEOPHYSICAL_TABLE in observations["tables"]
    if legacy_survey:
        observations = split_legacy_geophysical_bundle(observations)
    if observations is not None:
        observations = with_magnetic_log_schema(observations)
    if expedition_collected is None:
        expedition_collected = observations is not None and observations.get("stage") != "preliminary"
    public_observations = json.dumps(observations, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    public_recognition = json.dumps(recognition, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    if observation_config is None and observations is None:
        config_path = Path(__file__).resolve().parents[2] / "config/observations.json"
        observation_config = json.loads(config_path.read_text(encoding="utf-8"))
    preliminary_plan = None
    if observation_config is not None and observations is None and not legacy_survey:
        seed = data.get("seed", 0) if observation_seed is None else observation_seed
        if collect_endpoint:
            # The server prepares sampling coordinates and reads the true map
            # only after the user has requested collection.
            methods = {}
            if observation_config.get("geophysical_survey", {}).get("enabled") and "geophysics" in data:
                methods.update({table: observation_config["geophysical_survey"] for table in GEOPHYSICAL_TABLES.values()})
            for name in ("terrain_survey", "outcrops"):
                if observation_config.get(name, {}).get("enabled"):
                    methods[name] = observation_config[name]
            preliminary_plan = {"methods": methods}
        else:
            preliminary_plan = prepare_preliminary_survey(data, observation_config, seed)
        preliminary_plan["table_fields"] = {
            name: EXTRA_TABLE_FIELDS[name] for name in (*GEOPHYSICAL_TABLES.values(), "terrain_observations", "outcrop_observations")
        }
    manual_bundle = _manual_observation_bundle(data, observation_config) if observations is None and observation_config is not None else None
    embedded_plan = json.dumps(preliminary_plan, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    replacements = {
        "__WORKSPACE_STYLES__": WORKSPACE_STYLES,
        "__WORKSPACE_TABS__": WORKSPACE_TABS,
        "__WORKSPACE_PANELS__": WORKSPACE_PANELS,
        "__WORKSPACE_SCRIPT__": WORKSPACE_SCRIPT,
    }
    html = re.sub("|".join(replacements), lambda match: replacements[match.group()], HTML_TEMPLATE)
    # Insert each JSON literal once; strings inside the payload are never templates.
    reference_rocks = [{"id": rock["id"], "name": rock["name"], "color": rock["color"]}
                       for rock in data.get("rocks", [])]
    embedded_rocks = json.dumps(reference_rocks, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    workbook = Path(__file__).resolve().parents[2] / "templates/observations/manual/manual_observations.xlsx"
    template_bytes = base64.b64encode(workbook.read_bytes()).decode("ascii") if workbook.is_file() else ""
    data_replacements = {"__OBSERVATION_DATA__": public_observations, "__RECOGNITION_DATA__": public_recognition,
                         "__OBSERVATION_IMPORT_ROCKS__": embedded_rocks,
                         "__OBSERVATION_IMPORT_XLSX__": json.dumps(template_bytes),
                         "__MAP_DATA__": embedded, "__MAP_SEED_TEXT__": json.dumps(str(data.get("seed", 0))).replace("</", "<\\/"),
                         "__PRELIMINARY_PLAN__": embedded_plan,
                         "__MANUAL_OBSERVATION_DATA__": json.dumps(manual_bundle, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
                         "__PRELIMINARY_COLLECTED__": json.dumps(preliminary_collected),
                         "__COLLECT_ENDPOINT__": json.dumps(collect_endpoint),
                         "__EXPEDITION_ENDPOINT__": json.dumps(expedition_endpoint),
                         "__EXPEDITION_COLLECTED__": json.dumps(expedition_collected)}
    html = re.sub("|".join(data_replacements), lambda match: data_replacements[match.group()], html)
    output_path.write_text(html, encoding="utf-8")
    return output_path
