#!/usr/bin/env python3
"""
Code Extractor v2.0 — 极简版（LLM 格式化输出解析）

设计理念：不猜测 LLM 输出格式，而是通过 prompt 约束 LLM 用固定格式输出。
只识别一种格式: **[FILE]**: `path/to/file.ext`

优点：
- 零残留文件（LLM 不输出的就不会被提取）
- 零格式兼容问题（只有一种格式）
- 维护成本极低（~60 行代码）
"""

import re
import os
import json
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass


# ==================== 集中管理：代码文件扩展名 ====================
# 供全项目统一引用，避免多处硬编码

CODE_EXTENSIONS: Set[str] = {
    'py', 'js', 'ts', 'tsx', 'jsx', 'vue', 'svelte',
    'java', 'go', 'rs', 'c', 'cpp', 'h', 'hpp',
    'cs', 'php', 'rb', 'swift', 'kt',
    'html', 'css', 'scss', 'less', 'sass',
    'json', 'yaml', 'yml', 'toml', 'xml',
    'sql', 'sh', 'bash', 'ps1', 'bat',
    'md', 'txt', 'env', 'gitignore', 'dockerfile',
    'conf', 'cfg', 'ini', 'properties',
}

SOURCE_CODE_EXTENSIONS: Set[str] = {
    'py', 'js', 'ts', 'tsx', 'jsx', 'vue', 'java', 'go', 'rs',
    'php', 'rb', 'swift', 'kt', 'css', 'scss', 'html', 'json', 'yaml', 'yml',
}

CONFIG_EXTENSIONS: Set[str] = {
    'env', 'gitignore', 'dockerfile', 'toml', 'conf', 'cfg',
}

CODE_REVIEW_EXTENSIONS: Set[str] = {
    'py', 'js', 'ts', 'tsx', 'jsx', 'vue', 'java', 'go', 'rs', 'php',
    'rb', 'swift', 'kt', 'css', 'scss', 'html', 'sql', 'sh', 'json',
    'yaml', 'yml', 'toml', 'env', 'gitignore', 'dockerfile', 'conf',
}


@dataclass
class CodeFile:
    """表示提取出的代码文件"""
    path: str          # 文件路径 (如 "src/Database.php")
    content: str       # 文件内容
    language: str      # 编程语言 (如 "python", "javascript")
    
    def __post_init__(self):
        # 清理路径
        self.path = self.path.lstrip("./").lstrip("/\\")


class CodeExtractor:
    """代码提取器 v2.0 — 只认 [FILE] 标记格式"""
    
    # 常见编程语言映射
    LANG_MAP = {
        'py': 'python', 'python': 'python',
        'js': 'javascript', 'javascript': 'javascript', 'ts': 'typescript', 'typescript': 'typescript',
        'java': 'java', 'go': 'go', 'golang': 'go',
        'rs': 'rust', 'rust': 'rust',
        'c': 'c', 'cpp': 'cpp', 'cxx': 'cpp', 'h': 'c-header', 'hpp': 'cpp-header',
        'cs': 'csharp', 'php': 'php',
        'rb': 'ruby', 'ruby': 'ruby',
        'sh': 'shell', 'bash': 'shell', 'zsh': 'shell',
        'ps1': 'powershell', 'sql': 'sql',
        'html': 'html', 'htm': 'html',
        'css': 'css', 'scss': 'scss', 'sass': 'sass', 'less': 'less',
        'json': 'json', 'yaml': 'yml', 'yml': 'yaml',
        'xml': 'xml', 'md': 'markdown', 'markdown': 'markdown',
        'dockerfile': 'dockerfile', 'tf': 'terraform',
        'env': 'env', 'gitignore': 'gitignore',
        'txt': 'text', 'log': 'text',
    }
    
    # 核心：唯一识别的文件标记格式
    # 支持: **[FILE]**: path, **[FILE]**: `path`, [FILE]: path, 文件: path
    FILE_MARKER = re.compile(
        r'(?:^|\n)'                          # 行首或换行后
        r'\*{0,2}\s*'                        # 可选的前置加粗 **
        r'(?:\[FILE\]|文件|FILE)\s*'         # [FILE] 或 文件 或 FILE
        r'\*{0,2}\s*'                        # 可选的后置加粗 **
        r'[:：]\s*'                           # 冒号分隔符
        r'[`\[\]()]?'                         # 可选的反引号/括号
        r'(?P<filepath>[^\s\n`*\])]+?\.[\w]+)'  # 文件路径（必须含扩展名，排除空白/特殊符号）
        r'[`\[\]()]?'                        # 可选闭合符
        r'\s*\n',                             # 行尾
        re.MULTILINE | re.IGNORECASE
    )
    
    # 代码块匹配
    CODE_BLOCK = re.compile(
        r'```(?P<lang>\w+)?\s*\n'
        r'(?P<content>(?:.|\n)*?)'
        r'```',
        re.MULTILINE | re.DOTALL
    )
    
    def _detect_language(self, lang_tag: Optional[str], filepath: str) -> str:
        """根据语言标签或文件扩展名检测编程语言"""
        if lang_tag:
            lang = lang_tag.lower()
            return self.LANG_MAP.get(lang, lang)
        if '.' in filepath:
            ext = filepath.rsplit('.', 1)[-1].lower()
            return self.LANG_MAP.get(ext, ext)
        return 'text'
    
    def _is_valid_filepath(self, filepath: str) -> bool:
        """检查是否是有效的文件路径"""
        if not filepath or len(filepath) < 2:
            return False
        if '.' not in filepath:
            return False
        # 排除非文件路径
        invalid = ['http', 'true', 'false', 'null', 'import', 'class', 'def', 'function']
        if any(filepath.lower().startswith(p) for p in invalid):
            return False
        return True
    
    def _clean_content(self, content: str) -> str:
        """清理代码内容"""
        lines = content.split('\n')
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)
    
    def extract(self, text: str) -> List[CodeFile]:
        """
        从文本中提取代码文件
        
        只识别 **[FILE]**: `path` + ```code``` 格式
        """
        files = []
        
        # 找所有 [FILE] 标记
        file_markers = list(self.FILE_MARKER.finditer(text))
        
        for i, marker_match in enumerate(file_markers):
            filepath = marker_match.group('filepath').strip()
            
            if not self._is_valid_filepath(filepath):
                continue
            
            # 找该标记后的第一个代码块
            marker_end = marker_match.end()
            
            # 在标记之后搜索代码块
            search_region = text[marker_end:]
            block_match = self.CODE_BLOCK.search(search_region)
            
            if not block_match:
                continue
            
            lang_tag = block_match.group('lang')
            content = self._clean_content(block_match.group('content'))
            
            if not content or len(content) < 5:  # 过滤太短的内容（可能是示例）
                continue
            
            files.append(CodeFile(
                path=filepath,
                content=content,
                language=self._detect_language(lang_tag, filepath)
            ))
        
        # 去重：相同路径保留内容最长的
        seen = {}
        for f in files:
            if f.path in seen:
                if len(f.content) > len(seen[f.path].content):
                    seen[f.path] = f
            else:
                seen[f.path] = f
        
        return list(seen.values())
    
    def extract_with_info(self, text: str, project_name: str) -> Dict:
        """提取并返回统计信息"""
        files = self.extract(text)
        languages = list(set(f.language for f in files))
        total_lines = sum(len(f.content.split('\n')) for f in files)
        
        return {
            'project_name': project_name,
            'files': files,
            'file_count': len(files),
            'languages': languages,
            'total_lines': total_lines
        }
    
    def extract_with_structure(self, text: str, project_name: str) -> Dict:
        """
        提取代码文件并返回结构化统计信息（含目录树）
        
        用于项目文档生成，返回：
        - project_name: 项目名
        - file_count: 文件数量
        - languages: 涉及的编程语言
        - total_lines: 总代码行数
        - total_chars: 总字符数
        - directory_tree: 目录结构树（字符串）
        - file_details: 每个文件的路径/语言/行数详情
        """
        files = self.extract(text)
        languages = sorted(set(f.language for f in files))
        total_lines = sum(len(f.content.split('\n')) for f in files)
        total_chars = sum(len(f.content) for f in files)
        
        # 构建目录树
        tree = self._build_directory_tree(files)
        
        # 文件详情
        file_details = []
        for f in files:
            file_details.append({
                'path': f.path,
                'language': f.language,
                'lines': len(f.content.split('\n')),
                'chars': len(f.content),
            })
        
        return {
            'project_name': project_name,
            'file_count': len(files),
            'languages': languages,
            'total_lines': total_lines,
            'total_chars': total_chars,
            'directory_tree': tree,
            'file_details': file_details,
        }
    
    def _build_directory_tree(self, files: List[CodeFile]) -> str:
        """根据文件列表构建目录树字符串"""
        if not files:
            return "(no files)"
        
        # 构建嵌套字典表示目录结构
        root = {}
        for f in files:
            parts = f.path.replace('\\', '/').split('/')
            current = root
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            # 叶节点用 None 标记
            current[parts[-1]] = None
        
        # 递归生成树字符串
        def _render(node, prefix="", is_last=True):
            lines = []
            items = sorted(node.items(), key=lambda x: (x[1] is None, x[0]))
            for i, (name, child) in enumerate(items):
                is_last_item = (i == len(items) - 1)
                connector = "└── " if is_last_item else "├── "
                if child is None:
                    # 文件
                    lines.append(f"{prefix}{connector}{name}")
                else:
                    # 目录
                    lines.append(f"{prefix}{connector}{name}/")
                    extension = "    " if is_last_item else "│   "
                    lines.extend(_render(child, prefix + extension, is_last_item))
            return lines
        
        tree_lines = _render(root)
        return "\n".join(tree_lines)


# ==================== 模块解析 & 文件摘要 ====================

def parse_modules_from_design(design_text: str) -> List[Dict]:
    """
    从详细设计输出中解析模块列表。
    
    查找 JSON 代码块: {"modules": [{id, name, description, files}, ...]}
    如果找不到 JSON，回退到 Markdown 标题解析。
    
    Returns:
        [{"id": str, "name": str, "description": str, "files": [str]}, ...]
        空列表表示解析失败或无模块
    """
    if not design_text:
        return []
    
    # === 策略1: 解析 JSON 代码块 ===
    json_pattern = re.compile(
        r'```(?:json)?\s*\n\s*(\{.*?"modules".*?\})\s*\n```',
        re.DOTALL
    )
    json_match = json_pattern.search(design_text)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            modules = data.get("modules", [])
            if modules and isinstance(modules, list):
                # 校验并规范化
                result = []
                for m in modules:
                    if not isinstance(m, dict):
                        continue
                    mid = m.get("id", m.get("name", "unknown"))
                    if isinstance(mid, str):
                        mid = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', mid).strip('_') or "module"
                    result.append({
                        "id": mid,
                        "name": m.get("name", mid),
                        "description": m.get("description", ""),
                        "files": [str(f) for f in m.get("files", []) if isinstance(f, str)],
                    })
                if result:
                    return result
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    
    # === 策略2: Markdown 标题解析（兜底） ===
    # 匹配 ### 模块: xxx 或 ## 模块名 等模式
    section_pattern = re.compile(
        r'(?:^|\n)(#{2,4})\s+(?:模块[:：]?\s*|Module[:：]?\s*)(.+?)(?:\n|$)',
        re.MULTILINE
    )
    sections = list(section_pattern.finditer(design_text))
    
    if not sections:
        return []
    
    modules = []
    for i, match in enumerate(sections):
        section_name = match.group(2).strip()
        section_start = match.end()
        section_end = sections[i + 1].start() if i + 1 < len(sections) else len(design_text)
        section_text = design_text[section_start:section_end]
        
        # 提取文件列表（找所有含扩展名的路径）
        file_paths = re.findall(
            r'(?:^|\s|[`"\'])([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)(?:\s|$|[`"\',;])',
            section_text
        )
        # 过滤非文件路径
        file_paths = [f for f in file_paths if _is_likely_filepath(f)]
        
        mid = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', section_name).strip('_') or "module_%d" % i
        
        modules.append({
            "id": mid,
            "name": section_name,
            "description": section_text[:500].strip(),
            "files": file_paths,
        })
    
    return modules


def _is_likely_filepath(s: str) -> bool:
    """判断字符串是否像文件路径"""
    if not s or len(s) < 3 or '.' not in s:
        return False
    ext = s.rsplit('.', 1)[-1].lower()
    return ext in CODE_EXTENSIONS


def extract_exports_summary(project_path: str) -> str:
    """
    扫描项目目录中已写入的文件，提取导出摘要。
    
    对每个文件只保留：文件路径 + 导出的函数/类/组件签名（最多 5 行）
    用于传递给下一个模块的开发上下文，避免传递完整文件内容。
    """
    if not project_path or not os.path.isdir(project_path):
        return ""
    
    summaries = []
    
    for root, dirs, fnames in os.walk(project_path):
        # 跳过隐藏目录和 node_modules
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules' and d != '__pycache__']
        if os.path.basename(root) == 'stages':
            continue
        
        for fname in sorted(fnames):
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, project_path).replace('\\', '/')
            
            # 只处理代码文件
            ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
            if ext not in SOURCE_CODE_EXTENSIONS:
                # 配置文件只记录存在
                if ext in CONFIG_EXTENSIONS:
                    summaries.append("  %s (配置文件)" % rel_path)
                continue
            
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue
            
            if not content.strip():
                continue
            
            # 提取导出/定义行
            exports = _extract_export_lines(content, ext)
            
            if exports:
                summaries.append("  %s:" % rel_path)
                for exp in exports[:5]:
                    summaries.append("    - %s" % exp)
            else:
                # 没有明确导出的文件，记录前2行非空非注释行
                lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith(('#', '//', '/*', '*'))]
                if lines:
                    summaries.append("  %s: %s" % (rel_path, lines[0][:80]))
    
    if not summaries:
        return ""
    
    return "## 已有项目文件\n" + "\n".join(summaries)


def _extract_export_lines(content: str, ext: str) -> List[str]:
    """从文件内容中提取导出/定义行"""
    exports = []
    lines = content.split('\n')
    
    if ext in ('ts', 'tsx', 'js', 'jsx'):
        # JS/TS: export, export default, export const/function/class/interface/type, export { ... }
        for line in lines:
            stripped = line.strip()
            if re.match(r'^export\s+(default\s+)?(const|let|var|function|class|interface|type|enum|async\s+function)\s', stripped):
                exports.append(stripped.rstrip('{').strip())
                if len(exports) >= 5:
                    break
            elif re.match(r'^export\s+\{', stripped):
                # export { foo, bar, baz }
                exports.append(stripped.rstrip(';').strip())
                if len(exports) >= 5:
                    break
            elif re.match(r'^export\s+default\s+', stripped):
                exports.append(stripped.rstrip(';').strip())
                if len(exports) >= 5:
                    break
    
    elif ext == 'py':
        # Python: class, def (top-level only，零缩进)
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith('class ') or stripped.startswith('def ')) and line and not line[0].isspace():
                exports.append(stripped.rstrip(':').strip())
                if len(exports) >= 5:
                    break
    
    elif ext == 'go':
        # Go: func, type, var, const (capital = exported)
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('func ', 'type ', 'var ', 'const ')):
                exports.append(stripped.rstrip('{').strip())
                if len(exports) >= 5:
                    break
    
    elif ext in ('java', 'kt', 'swift'):
        # Java-like: public class/interface/enum, public func
        for line in lines:
            stripped = line.strip()
            if 'public ' in stripped and any(stripped.startswith(k) for k in ('public class', 'public interface', 'public enum', 'public func', 'public struct')):
                exports.append(stripped.rstrip('{').strip())
                if len(exports) >= 5:
                    break
    
    elif ext == 'php':
        # PHP: class, function, namespace
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('class ', 'function ', 'namespace ')) and line and not line[0].isspace():
                exports.append(stripped.rstrip('{').strip())
                if len(exports) >= 5:
                    break
    
    return exports


def extract_module_design_section(design_text: str, module: Dict) -> str:
    """
    从详细设计文档中提取与指定模块相关的设计内容。
    
    策略：
    1. 如果设计文档中有明确的模块标题段落，提取该段落
    2. 否则，搜索包含该模块文件路径的段落
    3. 都找不到则返回设计文档的前 3000 字符
    """
    if not design_text:
        return module.get("description", "")
    
    module_name = module.get("name", "")
    module_id = module.get("id", "")
    module_files = module.get("files", [])
    
    # 策略1: 查找模块标题段落
    # 匹配 ### 模块名 或 ## 模块名 等
    for name in [module_name, module_id]:
        if not name:
            continue
        # 转义正则特殊字符
        escaped = re.escape(name)
        pattern = re.compile(
            r'(?:^|\n)(#{2,4})\s+.*?(?:%s).*?\n' % escaped,
            re.IGNORECASE
        )
        match = pattern.search(design_text)
        if match:
            # 找到下一个同级或更高级标题的位置
            header_level = len(match.group(1))
            next_pattern = re.compile(
                r'\n#{1,%d}\s+' % header_level,
                re.MULTILINE
            )
            next_match = next_pattern.search(design_text, match.end())
            end = next_match.start() if next_match else len(design_text)
            section = design_text[match.start():end].strip()
            if len(section) > 200:  # 确保不是太短的匹配
                return section[:4000]
    
    # 策略2: 查找包含模块文件路径的段落
    for fpath in module_files[:3]:
        if not fpath:
            continue
        # 取文件名部分
        fname = fpath.rsplit('/', 1)[-1] if '/' in fpath else fpath
        if fname in design_text:
            # 找到该文件名附近的内容
            idx = design_text.index(fname)
            # 向前找段落开头
            start = max(0, idx - 500)
            # 向后找段落结尾
            end = min(len(design_text), idx + 2000)
            # 扩展到行边界
            start = design_text.rfind('\n', 0, start) + 1 if start > 0 else 0
            end = design_text.find('\n', end)
            if end == -1:
                end = len(design_text)
            section = design_text[start:end].strip()
            if len(section) > 200:
                return section[:4000]
    
    # 策略3: 回退 - 返回项目概览部分 + 模块描述
    overview = design_text[:3000]
    desc = module.get("description", "")
    if desc:
        return overview + "\n\n## 当前模块\n" + desc
    return overview


# 便捷函数
def extract_code(text: str) -> List[CodeFile]:
    """从文本中提取代码文件的便捷函数"""
    return CodeExtractor().extract(text)


if __name__ == '__main__':
    # 测试
    test_text = '''
## 编码开发阶段输出

**[FILE]**: `src/Database.php`
```php
<?php
/**
 * 数据库主类
 */
namespace Database;

class Database {
    private $pdo;
}
```

**[FILE]**: src/ConnectionPool.php
```php
<?php
namespace Database;

class ConnectionPool {
    private $pool = [];
}
```

[FILE]: composer.json
```json
{
  "name": "mysql-database",
  "type": "library"
}
```
'''
    
    extractor = CodeExtractor()
    result = extractor.extract(test_text)
    
    print(f"提取到 {len(result)} 个文件:")
    for f in result:
        print(f"  - {f.path} ({f.language}, {len(f.content)} 字符)")
