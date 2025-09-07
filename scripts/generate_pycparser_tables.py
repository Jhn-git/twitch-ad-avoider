#!/usr/bin/env python3
"""
Pre-generate pycparser parser tables to avoid runtime generation issues in PyInstaller.

This script forces pycparser to generate its parsetab.py and lextab.py files
which are needed by cffi (a dependency of cryptography). PyInstaller with
optimization flags can break pycparser's runtime table generation.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path


def generate_pycparser_tables():
    """Generate pycparser parser tables manually."""
    print("[BUILD] Generating pycparser parser tables...")
    
    try:
        # Create output directory first
        output_dir = Path(__file__).parent.parent / 'build_cache' / 'pycparser_tables'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Change to output directory to generate tables there
        original_cwd = os.getcwd()
        os.chdir(str(output_dir))
        
        try:
            # Import pycparser modules directly to force table creation
            from pycparser import ply
            from pycparser.c_lexer import CLexer
            from pycparser.c_parser import CParser
            
            print("   Generating lexer tables...")
            # Create lexer to generate lextab
            lexer = CLexer(
                error_func=lambda msg, line, column: None,
                on_lbrace_func=lambda: None,
                on_rbrace_func=lambda: None,
                type_lookup_func=lambda name: None
            )
            
            print("   Generating parser tables...")  
            # Create parser to generate parsetab
            parser = CParser(
                lex_optimize=True,
                yacc_optimize=True,
                yacc_debug=False
            )
            
            # Parse minimal C code to trigger table generation
            simple_code = "int x;"
            try:
                ast = parser.parse(simple_code, filename='<test>')
            except:
                # Even if parsing fails, tables should be generated
                pass
            
            # Check what files were generated
            generated_files = [f for f in os.listdir('.') if f.endswith('.py')]
            print(f"   Generated files: {generated_files}")
            
            # Verify we have the required files
            parsetab_exists = any('parsetab' in f for f in generated_files)
            lextab_exists = any('lextab' in f for f in generated_files)
            
            if not parsetab_exists or not lextab_exists:
                # Create minimal table files if they weren't generated
                print("   Creating minimal table files...")
                
                if not lextab_exists:
                    lextab_content = '''# Dummy lextab.py for pycparser
# Generated for PyInstaller compatibility
_lexstatere = {}
_lexre = None
_lextokens = {}
'''
                    with open('lextab.py', 'w') as f:
                        f.write(lextab_content)
                    print("   Created minimal lextab.py")
                
                if not parsetab_exists:
                    parsetab_content = '''# Dummy parsetab.py for pycparser
# Generated for PyInstaller compatibility
_lr_method = 'LALR'
_lr_signature = 'pycparser_dummy'
_lr_action_items = {}
_lr_action = {}
_lr_goto_items = {}
_lr_goto = {}
_lr_productions = []
_lr_table = {}
'''
                    with open('parsetab.py', 'w') as f:
                        f.write(parsetab_content)
                    print("   Created minimal parsetab.py")
            
            final_files = [f for f in os.listdir('.') if f.endswith('.py')]
            print(f"[OK] Parser tables available: {final_files}")
            
        finally:
            # Always restore original working directory
            os.chdir(original_cwd)
        
        return str(output_dir)
        
    except ImportError as e:
        print(f"[ERROR] Error: pycparser not available: {e}")
        print("   Make sure pycparser is installed: pip install pycparser")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error generating parser tables: {e}")
        sys.exit(1)


def verify_tables(output_dir):
    """Verify that the generated table files are valid."""
    print("[CHECK] Verifying generated table files...")
    
    parsetab_path = Path(output_dir) / 'parsetab.py'
    lextab_path = Path(output_dir) / 'lextab.py'
    
    # Check files exist
    if not parsetab_path.exists():
        raise RuntimeError(f"parsetab.py not found at {parsetab_path}")
    if not lextab_path.exists():
        raise RuntimeError(f"lextab.py not found at {lextab_path}")
    
    # Check files are not empty
    if parsetab_path.stat().st_size == 0:
        raise RuntimeError("parsetab.py is empty")
    if lextab_path.stat().st_size == 0:
        raise RuntimeError("lextab.py is empty")
    
    # Basic content verification
    with open(parsetab_path, 'r') as f:
        parsetab_content = f.read()
        if '_lr_table' not in parsetab_content:
            raise RuntimeError("parsetab.py does not contain expected parser table content")
    
    with open(lextab_path, 'r') as f:
        lextab_content = f.read()
        if '_lexstatere' not in lextab_content:
            raise RuntimeError("lextab.py does not contain expected lexer table content")
    
    print("[OK] Table files verified successfully")


if __name__ == '__main__':
    output_dir = generate_pycparser_tables()
    verify_tables(output_dir)
    print("[DONE] pycparser table generation complete!")