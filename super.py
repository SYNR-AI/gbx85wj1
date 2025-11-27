#!/usr/bin/env python3
"""
根据 deploy_server_ 开头的 shell 脚本推断部署命令
能够识别项目类型并推断正确的生产部署命令
"""
import os
import re
import json
import sys
import argparse
from pathlib import Path
from collections import Counter


def detect_project_type(project_dir):
    """检测项目类型"""
    project_path = Path(project_dir)
    
    # 检查 package.json
    package_json = project_path / 'package.json'
    if package_json.exists():
        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                pkg = json.load(f)
            
            scripts = pkg.get('scripts', {})
            dependencies = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
            
            # 检查 Vite
            if (project_path / 'vite.config.ts').exists() or (project_path / 'vite.config.js').exists():
                return {
                    'type': 'vite',
                    'category': 'static',
                    'build_command': 'npm run build',
                    'description': 'Vite 静态网页项目'
                }
            
            # 检查 Create React App
            if 'react-scripts' in dependencies:
                return {
                    'type': 'cra',
                    'category': 'static',
                    'build_command': 'npm run build',
                    'description': 'Create React App 项目'
                }
            
            # 检查 Vue CLI
            if '@vue/cli-service' in dependencies:
                return {
                    'type': 'vue-cli',
                    'category': 'static',
                    'build_command': 'npm run build',
                    'description': 'Vue CLI 项目'
                }
            
            # 通用前端项目（有 build 脚本）
            if 'build' in scripts:
                return {
                    'type': 'frontend',
                    'category': 'static',
                    'build_command': 'npm run build',
                    'description': '前端项目（通用）'
                }
            
        except Exception as e:
            pass
    
    return {
        'type': 'unknown',
        'category': 'unknown',
        'build_command': None,
        'description': '未知项目类型'
    }


def analyze_deploy_script(script_path):
    """分析单个部署脚本，提取部署命令"""
    script_dir = Path(script_path).parent
    
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]
    
    # 提取关键信息
    result = {
        'script': os.path.basename(script_path),
        'working_dir': None,
        'commands': [],
        'current_command': None,
        'project_type': None,
        'recommended_command': None
    }
    
    # 查找 cd 命令来确定工作目录
    cd_pattern = r'cd\s+(.+?)(?:\s|$)'
    for line in lines:
        cd_match = re.search(cd_pattern, line)
        if cd_match:
            result['working_dir'] = cd_match.group(1)
    
    # 提取所有命令（排除 cd）
    for line in lines:
        if line.startswith('cd '):
            continue
        if line:
            result['commands'].append(line)
    
    # 获取当前使用的命令（最后一个非 cd 命令）
    if result['commands']:
        result['current_command'] = result['commands'][-1]
    
    # 检测项目类型
    if result['working_dir']:
        project_path = script_dir / result['working_dir']
        if project_path.exists():
            result['project_type'] = detect_project_type(project_path)
            
            # 根据项目类型推荐部署命令
            if result['project_type']['build_command']:
                result['recommended_command'] = result['project_type']['build_command']
            else:
                result['recommended_command'] = result['current_command']
    
    return result


def infer_deploy_commands(target_dir=None):
    """主函数
    
    Args:
        target_dir: 目标目录的绝对路径，如果为 None 则使用脚本所在目录
    """
    if target_dir is None:
        print(f"错误: 未提供目标目录")
        return

    script_dir = Path(target_dir).resolve()
    if not script_dir.exists():
        print(f"错误: 目录不存在: {script_dir}")
        return
    
    deploy_scripts = list(script_dir.glob('deploy_server_*.sh'))
    
    if not deploy_scripts:
        print(f"在 {script_dir} 目录下未找到 deploy_server_*.sh 脚本")
        return
    
    print(f"找到 {len(deploy_scripts)} 个部署脚本:\n")
    print("=" * 80)
    
    results = []
    for script_path in sorted(deploy_scripts):
        result = analyze_deploy_script(script_path)
        results.append(result)
        
        print(f"\n脚本: {result['script']}")
        print("-" * 80)
        
        if result['working_dir']:
            print(f"工作目录: {result['working_dir']}")
        
        if result['project_type']:
            print(f"项目类型: {result['project_type']['description']}")
            print(f"  类别: {result['project_type']['category']}")
        
        if result['commands']:
            print(f"\n当前脚本中的命令:")
            for i, cmd in enumerate(result['commands'], 1):
                print(f"  {i}. {cmd}")
        
        if result['current_command']:
            print(f"\n当前使用的命令: {result['current_command']}")
        
        if result['recommended_command']:
            print(f"\n推荐的部署命令: {result['recommended_command']}")
            
            # 如果当前命令是开发命令，给出提示
            if result['current_command'] and 'dev' in result['current_command'].lower():
                if result['project_type'] and result['project_type']['category'] == 'static':
                    print(f"  ⚠️  注意: 当前使用的是开发服务器命令，生产环境应使用构建命令")
        else:
            print(f"\n⚠️  警告: 未能推断出推荐的部署命令")
    
    print("\n" + "=" * 80)
    print("\n总结:")
    print("-" * 80)
    
    # 输出简化的部署命令列表
    print("\n推荐的部署命令:")
    for result in results:
        if result['recommended_command']:
            project_info = f" ({result['project_type']['description']})" if result['project_type'] else ""
            print(f"  {result['script']}{project_info}:")
            print(f"    {result['recommended_command']}")
    
    # 统计项目类型
    project_types = [r['project_type']['type'] for r in results if r['project_type']]
    if project_types:
        type_counter = Counter(project_types)
        print("\n项目类型统计:")
        for ptype, count in type_counter.most_common():
            print(f"  {ptype}: {count} 个")
    
    # 生成 JSON 输出：数组格式，每个元素包含 dir、command 和 type
    deploy_commands_json = []
    for result in results:
        if result['working_dir'] and result['recommended_command']:
            # 只处理静态前端项目
            project_type_str = "frontend"
            if result['project_type']:
                category = result['project_type']['category']
                # 只保留静态前端项目（排除 ssr）
                if category != 'static':
                    continue  # 跳过非静态前端项目
            
            deploy_commands_json.append({
                "dir": result['working_dir'],
                "command": result['recommended_command'],
                "type": project_type_str
            })
    
    # 保存 JSON 文件
    json_output_path = script_dir / 'deploy_commands.json'
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(deploy_commands_json, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'=' * 80}")
    print(f"\nJSON 输出已保存到: {json_output_path}")
    print(f"\nJSON 内容:")
    print(json.dumps(deploy_commands_json, ensure_ascii=False, indent=2))
    
    return results, deploy_commands_json


def list_scripts(target_dir):
    """列出所有部署脚本"""
    script_dir = Path(target_dir).resolve()
    if not script_dir.exists():
        print(f"错误: 目录不存在: {script_dir}")
        return
    
    deploy_scripts = list(script_dir.glob('deploy_server_*.sh'))
    
    if not deploy_scripts:
        print(f"在 {script_dir} 目录下未找到 deploy_server_*.sh 脚本")
        return
    
    print(f"找到 {len(deploy_scripts)} 个部署脚本:\n")
    for script_path in sorted(deploy_scripts):
        print(f"  - {script_path.name}")


def output_json_only(target_dir):
    """只输出 JSON 格式"""
    script_dir = Path(target_dir).resolve()
    if not script_dir.exists():
        print(json.dumps({"error": f"目录不存在: {script_dir}"}, ensure_ascii=False))
        return
    
    deploy_scripts = list(script_dir.glob('deploy_server_*.sh'))
    
    if not deploy_scripts:
        print(json.dumps({"error": f"在 {script_dir} 目录下未找到 deploy_server_*.sh 脚本"}, ensure_ascii=False))
        return
    
    results = []
    for script_path in sorted(deploy_scripts):
        result = analyze_deploy_script(script_path)
        results.append(result)
    
    deploy_commands_json = []
    for result in results:
        if result['working_dir'] and result['recommended_command']:
            project_type_str = "frontend"
            if result['project_type']:
                category = result['project_type']['category']
                if category != 'static':
                    continue
            
            deploy_commands_json.append({
                "dir": result['working_dir'],
                "command": result['recommended_command'],
                "type": project_type_str
            })
    
    print(json.dumps(deploy_commands_json, ensure_ascii=False, indent=2))


def generate_shell_script(target_dir, output_path=None):
    """生成shell脚本，包含进入目录、执行构建命令、复制dist产物到/website目录
    
    Args:
        target_dir: 目标目录的绝对路径
        output_path: 输出脚本的路径，如果为 None 则输出到标准输出
    """
    script_dir = Path(target_dir).resolve()
    if not script_dir.exists():
        error_msg = f"错误: 目录不存在: {script_dir}"
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"#!/bin/bash\n# {error_msg}\n")
        else:
            print(error_msg)
        return
    
    deploy_scripts = list(script_dir.glob('deploy_server_*.sh'))
    
    if not deploy_scripts:
        error_msg = f"在 {script_dir} 目录下未找到 deploy_server_*.sh 脚本"
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"#!/bin/bash\n# {error_msg}\n")
        else:
            print(error_msg)
        return
    
    # 分析所有部署脚本
    results = []
    for script_path in sorted(deploy_scripts):
        result = analyze_deploy_script(script_path)
        results.append(result)
    
    # 生成shell脚本内容
    script_lines = [
        "#!/bin/bash",
        "# 自动生成的部署脚本",
        "# 功能: 进入目录、执行构建命令、复制dist产物到/website目录",
        "",
        "set -e  # 遇到错误立即退出",
        "",
        f"# 输出目录",
        f"OUTPUT_DIR=\"$1\"",
        f"# 脚本基础目录",
        f"BASE_DIR=\"{script_dir}\"",
        f"cd \"$BASE_DIR\"",
        "",
    ]
    
    # 为每个项目生成脚本片段
    for result in results:
        if not result['working_dir'] or not result['recommended_command']:
            continue
        
        # 只处理静态前端项目
        if result['project_type']:
            category = result['project_type']['category']
            if category != 'static':
                continue

        working_dir = result['working_dir']
        build_command = result['recommended_command']

        # 如果项目类型是静态前端项目，则需要在构建命令前执行安装依赖命令
        if result['project_type'] and result['project_type']['category'] == 'static':
            build_command = f"npm install && {build_command}"
        
        # 添加注释说明
        script_lines.append(f"# 项目: {result['script']}")
        if result['project_type']:
            script_lines.append(f"# 类型: {result['project_type']['description']}")
        script_lines.append("")
        
        # cd 到工作目录（相对于BASE_DIR）
        script_lines.append(f"echo \"进入目录: {working_dir}\"")
        script_lines.append(f"cd \"$BASE_DIR/{working_dir}\"")
        script_lines.append("")
        
        # 执行构建命令
        script_lines.append(f"echo \"执行构建命令: {build_command}\"")
        script_lines.append(build_command)
        script_lines.append("")
        
        # 复制dist产物到/website目录
        script_lines.append(f"echo \"复制dist产物到{"${OUTPUT_DIR}"}目录\"")
        script_lines.append(f"if [ -d \"$BASE_DIR/{working_dir}/dist\" ]; then")
        script_lines.append(f"    mkdir -p $OUTPUT_DIR")
        script_lines.append(f"    cp -r dist/* $OUTPUT_DIR")
        script_lines.append("    echo \"复制完成\"")
        script_lines.append("else")
        script_lines.append("    echo \"警告: dist目录不存在，跳过复制\"")
        script_lines.append("fi")
        script_lines.append("")
        script_lines.append("echo \"---\"")
        script_lines.append("")
    
    script_content = "\n".join(script_lines)
    
    # 输出脚本
    if output_path:
        output_file = Path(output_path)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        # 添加执行权限
        os.chmod(output_file, 0o755)
        print(f"Shell脚本已生成: {output_file}")
    else:
        print(script_content)


def main():
    """主函数，处理命令行参数和子命令"""
    parser = argparse.ArgumentParser(
        description='根据 deploy_server_ 开头的 shell 脚本推断部署命令',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用子命令', metavar='COMMAND')
    
    # analyze 子命令（默认）
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='完整分析部署脚本并显示详细信息（默认命令）'
    )
    analyze_parser.add_argument(
        'target_dir',
        help='目标目录的绝对路径'
    )
    
    # list 子命令
    list_parser = subparsers.add_parser(
        'list',
        help='只列出找到的部署脚本'
    )
    list_parser.add_argument(
        'target_dir',
        help='目标目录的绝对路径'
    )
    
    # json 子命令
    json_parser = subparsers.add_parser(
        'json',
        help='只输出 JSON 格式的部署命令'
    )
    json_parser.add_argument(
        'target_dir',
        help='目标目录的绝对路径'
    )
    
    # script 子命令
    script_parser = subparsers.add_parser(
        'script',
        help='生成shell脚本（进入目录、执行构建、复制dist到/website）'
    )
    script_parser.add_argument(
        'target_dir',
        help='目标目录的绝对路径'
    )
    script_parser.add_argument(
        '-o', '--output',
        dest='output_path',
        help='输出脚本的路径（如果不指定则输出到标准输出）'
    )
    
    args = parser.parse_args()
    
    # 如果没有提供子命令，默认使用 analyze，并尝试从参数中获取目录
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    # 根据子命令执行相应操作
    if args.command == 'analyze':
        infer_deploy_commands(args.target_dir)
    elif args.command == 'list':
        list_scripts(args.target_dir)
    elif args.command == 'json':
        output_json_only(args.target_dir)
    elif args.command == 'script':
        generate_shell_script(args.target_dir, getattr(args, 'output_path', None))


if __name__ == '__main__':
    main()

