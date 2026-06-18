import marimo

app = marimo.App()

@app.cell
def _(mo):
    mo.md("hello world")
    return

if __name__ == "__main__":
    app.run()