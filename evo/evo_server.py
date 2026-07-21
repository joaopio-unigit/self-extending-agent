import os
import subprocess
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

@mcp.tool()
async def create_file(file_name: str, directory: str = ".", content: str = "") -> str:
    """Create a new file or overwrite an existing one with the provided content.

    Args:
        file_name: Name of the file to create or update
        directory: Optional directory where the file should be created
        content: Optional content to write to the file
    """
    try:
        os.makedirs(directory, exist_ok=True)
    except Exception as e:
        return f"Error creating directory '{directory}': {str(e)}"

    file_path = os.path.join(directory, file_name)

    if os.path.isdir(file_path):
        return f"Error: '{file_path}' is a directory."

    try:
        exists_before = os.path.exists(file_path)
        with open(file_path, 'w') as f:
            f.write(content)

        action = "updated" if exists_before else "created"
        return f"File '{file_name}' {action} in directory '{directory}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"

@mcp.tool()
async def read_file(file_path: str) -> str:
    """Read the content of a file.

    Args:
        file_path: Path to the file to read
    """
    if not os.path.isfile(file_path):
        return f"Error: File '{file_path}' does not exist."

    with open(file_path, 'r') as f:
        content = f.read()

    return content


@mcp.tool()
async def delete_file(file_path: str) -> str:
    """Delete a file from the filesystem.

    Args:
        file_path: Path to the file to delete
    """
    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' does not exist."
    
    if not os.path.isfile(file_path):
        return f"Error: '{file_path}' is not a file."
    
    try:
        os.remove(file_path)
        return f"File '{file_path}' has been successfully deleted."
    except Exception as e:
        return f"Error deleting file: {str(e)}"

@mcp.tool()
async def run_command(command: str, directory: str = ".") -> str:
    """Run a shell command in the specified directory.

    Args:
        command: The shell command to run
        directory: Optional directory in which to run the command
    """
    if not os.path.isdir(directory):
        return f"Error: Directory '{directory}' does not exist."

    try:
        result = subprocess.run(command, shell=True, cwd=directory, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Error running command: {result.stderr}"
        return result.stdout
    except Exception as e:
        return f"Exception occurred while running command: {str(e)}"

def main():
    # Initialize and run the server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
