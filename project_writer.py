#!/usr/bin/env python3
"""
Project Writer Module - 将提取的代码写入项目目录

功能:
1. 创建项目目录结构
2. 写入代码文件
3. 生成项目 README
4. 生成文件清单
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import asdict

from code_extractor import CodeFile
from constants import STAGE_NAMES, STAGE_NAMES_NUMBERED


class ProjectWriter:
    """项目写入器 - 管理项目文件系统"""
    
    def __init__(self, base_dir: str):
        """
        Args:
            base_dir: 项目根目录 (如 "project/")
        """
        self.base_dir = base_dir
        self._ensure_base_dir()
    
    def _ensure_base_dir(self):
        """确保基础目录存在"""
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir, exist_ok=True)
    
    def _sanitize_project_name(self, name: str) -> str:
        """
        清理项目名称，确保可用于文件路径
        
        替换非法字符为下划线
        """
        import re
        # 替换文件系统非法字符
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
        # 移除首尾空格和点
        sanitized = sanitized.strip(' .')
        # 限制长度
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized or 'untitled_project'
    
    def _get_project_path(self, project_name: str) -> str:
        """获取项目目录路径"""
        safe_name = self._sanitize_project_name(project_name)
        return os.path.join(self.base_dir, safe_name)
    
    def create_project_directory(self, project_name: str) -> str:
        """
        创建项目目录
        
        Returns:
            str: 项目目录的完整路径
        """
        project_path = self._get_project_path(project_name)
        
        # 创建主要子目录
        subdirs = ['src', 'docs', 'config', 'tests']
        for subdir in subdirs:
            path = os.path.join(project_path, subdir)
            os.makedirs(path, exist_ok=True)
        
        return project_path
    
    def write_file(self, project_name: str, code_file: CodeFile) -> str:
        """
        写入单个代码文件
        
        Args:
            project_name: 项目名称
            code_file: 代码文件对象
            
        Returns:
            str: 写入的文件路径
        """
        project_path = self._get_project_path(project_name)
        
        # 路径遍历检查：防止 .. 组件和绝对路径
        norm_path = os.path.normpath(code_file.path)
        if norm_path.startswith('..') or os.path.isabs(norm_path):
            raise ValueError(f"非法路径: '{code_file.path}' 超出项目目录")
        
        # 解析目标路径
        target_path = os.path.join(project_path, code_file.path)
        
        # 路径遍历检查：确保目标路径在项目目录内（Windows 大小写不敏感）
        real_target = os.path.realpath(target_path)
        real_project = os.path.realpath(project_path)
        if not (os.path.normcase(real_target).startswith(os.path.normcase(real_project + os.sep))
                or os.path.normcase(real_target) == os.path.normcase(real_project)):
            raise ValueError(f"路径遍历攻击: '{code_file.path}' 超出项目目录")
        
        # 确保父目录存在
        parent_dir = os.path.dirname(target_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        
        # 写入文件
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(code_file.content)
        
        return target_path
    
    def write_files(self, project_name: str, files: List[CodeFile]) -> List[str]:
        """
        批量写入代码文件
        
        Args:
            project_name: 项目名称
            files: 代码文件列表
            
        Returns:
            List[str]: 写入的文件路径列表
        """
        written = []
        for code_file in files:
            path = self.write_file(project_name, code_file)
            written.append(path)
        return written
    
    def generate_readme(self, project_name: str, description: str = '', 
                        stages_output: Dict[str, str] = None,
                        files_info: Dict = None) -> str:
        """
        生成项目 README.md
        
        Args:
            project_name: 项目名称
            description: 项目描述
            stages_output: 各阶段输出 {stage_id: output_text}
            files_info: 文件信息 {'file_count': int, 'languages': List[str], ...}
            
        Returns:
            str: README 文件路径
        """
        project_path = self._get_project_path(project_name)
        readme_path = os.path.join(project_path, 'README.md')
        
        lines = []
        lines.append(f'# {project_name}')
        lines.append('')
        
        if description:
            lines.append(f'{description}')
            lines.append('')
        
        lines.append(f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        lines.append('')
        
        # 文件统计
        if files_info:
            lines.append('## 项目统计')
            lines.append('')
            lines.append(f'- 文件数量: {files_info.get("file_count", 0)}')
            lines.append(f'- 编程语言: {", ".join(files_info.get("languages", []))}')
            lines.append(f'- 总行数: {files_info.get("total_lines", 0)}')
            lines.append('')
        
        # 目录结构
        lines.append('## 目录结构')
        lines.append('')
        lines.append('```')
        lines.append(self._generate_tree(project_path))
        lines.append('```')
        lines.append('')
        
        # 工作流阶段摘要
        if stages_output:
            lines.append('## 开发流程')
            lines.append('')
            
            stage_names = STAGE_NAMES
            
            for stage_id, stage_name in stage_names.items():
                if stage_id in stages_output:
                    lines.append(f'### {stage_name}')
                    lines.append('')
                    # 只取前500字符作为摘要
                    summary = stages_output[stage_id][:500].strip()
                    if len(stages_output[stage_id]) > 500:
                        summary += '\n\n...(详见 docs/stages/)'
                    lines.append(summary)
                    lines.append('')
        
        # 写入 README
        content = '\n'.join(lines)
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return readme_path
    
    def save_stage_outputs(self, project_name: str, stages_output: Dict[str, str]):
        """
        保存各阶段原始输出到 docs/stages/
        
        Args:
            project_name: 项目名称
            stages_output: 各阶段输出 {stage_id: output_text}
        """
        project_path = self._get_project_path(project_name)
        stages_dir = os.path.join(project_path, 'docs', 'stages')
        os.makedirs(stages_dir, exist_ok=True)
        
        stage_names = STAGE_NAMES_NUMBERED
        
        for stage_id, content in stages_output.items():
            filename = stage_names.get(stage_id, stage_id) + '.md'
            filepath = os.path.join(stages_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def generate_manifest(self, project_name: str, files: List[CodeFile]) -> str:
        """
        生成文件清单 manifest.json
        
        Args:
            project_name: 项目名称
            files: 代码文件列表
            
        Returns:
            str: manifest 文件路径
        """
        project_path = self._get_project_path(project_name)
        manifest_path = os.path.join(project_path, 'manifest.json')
        
        manifest = {
            'project_name': project_name,
            'generated_at': datetime.now().isoformat(),
            'files': [
                {
                    'path': f.path,
                    'language': f.language,
                    'size': len(f.content),
                    'lines': len(f.content.split('\n'))
                }
                for f in files
            ],
            'summary': {
                'total_files': len(files),
                'languages': list(set(f.language for f in files)),
                'total_lines': sum(len(f.content.split('\n')) for f in files),
                'total_size': sum(len(f.content) for f in files)
            }
        }
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        return manifest_path
    
    def _generate_tree(self, path: str, prefix: str = '', max_depth: int = 10) -> str:
        """生成目录树文本（带递归深度限制，防止符号链接循环）"""
        if max_depth <= 0:
            return prefix + '...'
        
        lines = []
        try:
            items = sorted(os.listdir(path))
        except PermissionError:
            return prefix + '(权限不足)'
        
        # 过滤隐藏文件和特定目录
        items = [i for i in items if not i.startswith('.') and i not in ['__pycache__', '*.pyc']]
        
        for i, item in enumerate(items):
            item_path = os.path.join(path, item)
            is_last = i == len(items) - 1
            
            if is_last:
                connector = '└── '
                new_prefix = prefix + '    '
            else:
                connector = '├── '
                new_prefix = prefix + '│   '
            
            lines.append(prefix + connector + item)
            
            # 跳过符号链接，防止循环；限制递归深度
            if os.path.isdir(item_path) and not os.path.islink(item_path):
                lines.append(self._generate_tree(item_path, new_prefix, max_depth - 1))
        
        return '\n'.join(lines)
    
    def write_complete_project(self, project_name: str, 
                               description: str = '',
                               stages_output: Dict[str, str] = None,
                               code_files: List[CodeFile] = None) -> Dict:
        """
        写入完整项目（一站式方法）
        
        Args:
            project_name: 项目名称
            description: 项目描述
            stages_output: 各阶段输出 {stage_id: output_text}
            code_files: 提取的代码文件列表
            
        Returns:
            Dict: {
                'project_path': str,
                'files_written': List[str],
                'readme_path': str,
                'manifest_path': str
            }
        """
        # 创建项目目录
        project_path = self.create_project_directory(project_name)
        
        files_written = []
        
        # 写入代码文件
        if code_files:
            written = self.write_files(project_name, code_files)
            files_written.extend(written)
        
        # 保存阶段输出
        if stages_output:
            self.save_stage_outputs(project_name, stages_output)
        
        # 生成文件信息
        files_info = None
        if code_files:
            # 直接从已有的 code_files 构建统计信息，无需重新提取
            languages = sorted(set(f.language for f in code_files))
            total_lines = sum(len(f.content.split('\n')) for f in code_files)
            total_chars = sum(len(f.content) for f in code_files)
            
            from code_extractor import CodeExtractor
            extractor = CodeExtractor()
            tree = extractor._build_directory_tree(code_files)
            
            file_details = []
            for f in code_files:
                file_details.append({
                    'path': f.path,
                    'language': f.language,
                    'lines': len(f.content.split('\n')),
                    'chars': len(f.content),
                })
            
            files_info = {
                'project_name': project_name,
                'file_count': len(code_files),
                'languages': languages,
                'total_lines': total_lines,
                'total_chars': total_chars,
                'directory_tree': tree,
                'file_details': file_details,
            }
        
        # 生成 README
        readme_path = self.generate_readme(
            project_name, description, stages_output, files_info
        )
        
        # 生成 manifest
        manifest_path = None
        if code_files:
            manifest_path = self.generate_manifest(project_name, code_files)
        
        return {
            'project_path': project_path,
            'files_written': files_written,
            'readme_path': readme_path,
            'manifest_path': manifest_path,
            'file_count': len(code_files) if code_files else 0
        }


# 便捷函数
def get_default_project_base_dir() -> str:
    """获取默认项目基础目录"""
    # 首先检查环境变量
    env_dir = os.getenv('CREWAI_PROJECTS_DIR')
    if env_dir:
        return env_dir
    
    # 使用相对于 skill 目录的 project 文件夹
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(skill_dir, 'project')


def create_project_writer(base_dir: Optional[str] = None) -> ProjectWriter:
    """创建项目写入器的便捷函数"""
    if base_dir is None:
        base_dir = get_default_project_base_dir()
    return ProjectWriter(base_dir)


if __name__ == '__main__':
    # 测试
    from code_extractor import CodeFile
    
    writer = ProjectWriter('test_projects')
    
    test_files = [
        CodeFile(path='src/main.py', content='print("Hello")', language='python'),
        CodeFile(path='src/utils.py', content='def helper(): pass', language='python'),
        CodeFile(path='README.md', content='# Test', language='markdown'),
    ]
    
    result = writer.write_complete_project(
        project_name='TestProject',
        description='这是一个测试项目',
        code_files=test_files
    )
    
    print(f"项目已创建: {result['project_path']}")
    print(f"写入文件数: {result['file_count']}")
    print(f"README: {result['readme_path']}")
