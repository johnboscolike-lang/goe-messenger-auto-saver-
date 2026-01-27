"""
GOE Messenger MCP Server
Claude Code 연동을 위한 MCP(Model Context Protocol) 서버

사용법:
    # 직접 실행
    python -m mcp.server

    # Claude Code 설정
    ~/.claude/claude_desktop_config.json 에 추가:
    {
        "mcpServers": {
            "goe-messenger": {
                "command": "python",
                "args": ["-m", "mcp.server"],
                "cwd": "/path/to/goe-messenger-auto-saver"
            }
        }
    }
"""

import sys
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

# 상위 디렉토리를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# MCP 라이브러리 import (없으면 간단한 stdio 서버로 동작)
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        CallToolResult,
        ListToolsResult,
    )
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("MCP 라이브러리가 설치되지 않았습니다. 간단한 stdio 모드로 실행합니다.", file=sys.stderr)

# 도구 import
from mcp.tools import TOOLS

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger('goe-mcp-server')


# ============================================================
# MCP 서버 (mcp 라이브러리 사용)
# ============================================================

if HAS_MCP:
    # MCP 서버 인스턴스
    server = Server("goe-messenger")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        """사용 가능한 도구 목록 반환"""
        tools = []

        for name, info in TOOLS.items():
            # 파라미터 스키마 생성
            properties = {}
            required = []

            for param_name, param_info in info.get('parameters', {}).items():
                prop = {
                    'type': param_info.get('type', 'string'),
                    'description': param_info.get('description', '')
                }

                if 'default' in param_info:
                    prop['default'] = param_info['default']

                properties[param_name] = prop

                if param_info.get('required', False):
                    required.append(param_name)

            input_schema = {
                'type': 'object',
                'properties': properties
            }

            if required:
                input_schema['required'] = required

            tools.append(Tool(
                name=name,
                description=info['description'],
                inputSchema=input_schema
            ))

        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """도구 실행"""
        logger.info(f"도구 호출: {name}, 인자: {arguments}")

        if name not in TOOLS:
            return [TextContent(
                type="text",
                text=json.dumps({
                    'error': f'알 수 없는 도구: {name}'
                }, ensure_ascii=False)
            )]

        try:
            # 도구 함수 실행
            tool_func = TOOLS[name]['function']
            result = tool_func(**arguments)

            # 결과를 JSON으로 변환
            result_json = json.dumps(result, ensure_ascii=False, indent=2)

            logger.info(f"도구 결과: {name} - 성공")

            return [TextContent(
                type="text",
                text=result_json
            )]

        except Exception as e:
            logger.error(f"도구 실행 오류: {name} - {e}")
            return [TextContent(
                type="text",
                text=json.dumps({
                    'error': str(e),
                    'tool': name
                }, ensure_ascii=False)
            )]

    async def run_mcp_server():
        """MCP 서버 실행"""
        logger.info("GOE Messenger MCP 서버 시작...")

        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )


# ============================================================
# 간단한 Stdio 서버 (MCP 라이브러리 없을 때)
# ============================================================

class SimpleStdioServer:
    """MCP 라이브러리 없이 동작하는 간단한 JSON-RPC 서버"""

    def __init__(self):
        self.tools = TOOLS

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """요청 처리"""
        method = request.get('method', '')
        params = request.get('params', {})
        request_id = request.get('id')

        if method == 'tools/list':
            return self._list_tools(request_id)
        elif method == 'tools/call':
            return self._call_tool(request_id, params)
        elif method == 'initialize':
            return self._initialize(request_id)
        else:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32601,
                    'message': f'Method not found: {method}'
                }
            }

    def _initialize(self, request_id) -> Dict[str, Any]:
        """초기화 응답"""
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'protocolVersion': '2024-11-05',
                'serverInfo': {
                    'name': 'goe-messenger',
                    'version': '1.0.0'
                },
                'capabilities': {
                    'tools': {}
                }
            }
        }

    def _list_tools(self, request_id) -> Dict[str, Any]:
        """도구 목록 반환"""
        tools = []

        for name, info in self.tools.items():
            properties = {}
            required = []

            for param_name, param_info in info.get('parameters', {}).items():
                properties[param_name] = {
                    'type': param_info.get('type', 'string')
                }
                if param_info.get('required', False):
                    required.append(param_name)

            tools.append({
                'name': name,
                'description': info['description'],
                'inputSchema': {
                    'type': 'object',
                    'properties': properties,
                    'required': required
                }
            })

        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'tools': tools
            }
        }

    def _call_tool(self, request_id, params: Dict[str, Any]) -> Dict[str, Any]:
        """도구 실행"""
        name = params.get('name', '')
        arguments = params.get('arguments', {})

        if name not in self.tools:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32602,
                    'message': f'Unknown tool: {name}'
                }
            }

        try:
            tool_func = self.tools[name]['function']
            result = tool_func(**arguments)

            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'content': [{
                        'type': 'text',
                        'text': json.dumps(result, ensure_ascii=False, indent=2)
                    }]
                }
            }

        except Exception as e:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32000,
                    'message': str(e)
                }
            }

    def run(self):
        """서버 실행 (stdin/stdout)"""
        logger.info("GOE Messenger 간단한 stdio 서버 시작...")

        while True:
            try:
                # stdin에서 한 줄 읽기
                line = sys.stdin.readline()

                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                # JSON 파싱
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 파싱 오류: {e}")
                    continue

                # 요청 처리
                response = self.handle_request(request)

                # 응답 출력
                print(json.dumps(response, ensure_ascii=False), flush=True)

            except KeyboardInterrupt:
                logger.info("서버 종료...")
                break
            except Exception as e:
                logger.error(f"서버 오류: {e}")


# ============================================================
# CLI 인터페이스
# ============================================================

def run_cli():
    """CLI 모드로 실행"""
    import argparse

    parser = argparse.ArgumentParser(description='GOE Messenger MCP Server')
    parser.add_argument('--list-tools', action='store_true', help='사용 가능한 도구 목록 출력')
    parser.add_argument('--call', metavar='TOOL', help='도구 실행')
    parser.add_argument('--args', metavar='JSON', default='{}', help='도구 인자 (JSON)')

    args = parser.parse_args()

    if args.list_tools:
        print("\n사용 가능한 MCP 도구:")
        print("=" * 60)
        for name, info in TOOLS.items():
            print(f"\n{name}")
            print(f"  설명: {info['description']}")
            if info.get('parameters'):
                print("  파라미터:")
                for p_name, p_info in info['parameters'].items():
                    req = " (필수)" if p_info.get('required') else ""
                    default = f" [기본: {p_info['default']}]" if 'default' in p_info else ""
                    print(f"    - {p_name}: {p_info.get('type', 'string')}{req}{default}")
        return

    if args.call:
        tool_name = args.call

        if tool_name not in TOOLS:
            print(f"오류: 알 수 없는 도구 '{tool_name}'")
            return

        try:
            arguments = json.loads(args.args)
        except json.JSONDecodeError as e:
            print(f"오류: JSON 파싱 실패 - {e}")
            return

        tool_func = TOOLS[tool_name]['function']
        result = tool_func(**arguments)

        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 인자 없으면 서버 모드로 실행
    if HAS_MCP:
        asyncio.run(run_mcp_server())
    else:
        server = SimpleStdioServer()
        server.run()


# ============================================================
# 메인
# ============================================================

def main():
    """메인 엔트리포인트"""
    # 인자가 있으면 CLI 모드
    if len(sys.argv) > 1:
        run_cli()
    else:
        # 서버 모드
        if HAS_MCP:
            asyncio.run(run_mcp_server())
        else:
            server = SimpleStdioServer()
            server.run()


if __name__ == "__main__":
    main()
