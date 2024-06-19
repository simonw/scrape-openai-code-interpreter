import argparse
import io
import openai
import pathlib
import textwrap
import zipfile


def run(prompt, output_dir=None, output_file=None):
    assert (
        output_dir or output_file
    ), "You must provide either an output directory or an output file."
    client = openai.OpenAI()
    assistant = client.beta.assistants.create(
        name="Scrape internals",
        instructions="You create zip files.",
        tools=[{"type": "code_interpreter"}],
        model="gpt-4o",
    )
    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id, role="user", content=prompt
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id, assistant_id=assistant.id
    )
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    # Print out all messages here
    print(messages)
    file_id = messages.data[0].content[0].text.annotations[0].file_path.file_id
    if output_dir is not None:
        zip_file_data = client.files.content(file_id).read()
        with zipfile.ZipFile(io.BytesIO(zip_file_data)) as zip_ref:
            zip_ref.extractall(output_dir)
    else:
        # Write to file instead
        with open(output_file, "wb") as f:
            f.write(client.files.content(file_id).read())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output_dir", nargs="?", default=".", help="Directory to save output to"
    )
    args = parser.parse_args()

    root = pathlib.Path(args.output_dir)
    run(
        textwrap.dedent(
            r"""
        Use your Python tool to run os.listdir('.') and show the results.
        If that works try running this:

        import shutil;
        shutil.make_archive('openai_internal', 'zip', '.openai_internal')

        Then let me download the resulting file.
        """
        ),
        output_dir=str(root / "openai_internal"),
    )
    run(
        textwrap.dedent(
            r"""
        Run the following Python code with your Python tool:

        import pkg_resources

        def generate_requirements_txt():
            installed_packages = pkg_resources.working_set
            return '\n'.join(
                f"{package.key}=={package.version}"
                for package in sorted(installed_packages)
            )

        Then write the results to a file called packages.txt and let me download it.
        """
        ),
        output_file=str(root / "packages.txt"),
    )
