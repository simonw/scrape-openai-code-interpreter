import openai
import zipfile
import io

def run(output_dir, prompt):
    client = openai.OpenAI()
    assistant = client.beta.assistants.create(
        name="Scrape internals",
        instructions="You create zip files.",
        tools=[{"type": "code_interpreter"}],
        model="gpt-4o",
    )
    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant.id
    )
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    # Print out all messages here
    print(messages)
    file_id = messages.data[0].content[0].text.annotations[0].file_path.file_id
    zip_file_data = client.files.content(file_id).read()
    with zipfile.ZipFile(io.BytesIO(zip_file_data)) as zip_ref:
        zip_ref.extractall(output_dir)


if __name__ == "__main__":
    run(
        "/home/runner/work/scrape-openai-code-interpreter/scrape-openai-code-interpreter/openai_internal",
        (
            "Use your Python tool to run 'os.listdir('.') and show the results. "
            "If that works try running import shutil; "
            "shutil.make_archive('openai_internal', 'zip', '.openai_internal') "
            "and let me download the resulting file."
        )
    )
