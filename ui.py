import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk

from consulta_snmp import processar_planilha


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Consulta SNMP de Impressoras")
        self.root.geometry("620x420")
        self.root.resizable(False, False)

        self.arquivo_selecionado = tk.StringVar()

        self._criar_componentes()

    def _criar_componentes(self):
        frame_top = tk.Frame(self.root, padx=10, pady=10)
        frame_top.pack(fill=tk.X)

        tk.Label(frame_top, text="Arquivo de entrada:", anchor="w").pack(fill=tk.X)

        caminho_frame = tk.Frame(frame_top)
        caminho_frame.pack(fill=tk.X, pady=(4, 8))

        self.caminho_entry = tk.Entry(caminho_frame, textvariable=self.arquivo_selecionado, width=60)
        self.caminho_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_selecionar = tk.Button(caminho_frame, text="Selecionar arquivo", command=self.selecionar_arquivo)
        btn_selecionar.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_iniciar = tk.Button(self.root, text="Iniciar consulta", command=self.iniciar_consulta, width=20)
        self.btn_iniciar.pack(pady=(0, 10))

        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100, value=0)
        self.progress.pack(fill=tk.X, padx=10, pady=(0, 4))

        self.progress_label = tk.Label(self.root, text="0/0 IPs processados", anchor="w")
        self.progress_label.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(self.root, text="Log de execução:", anchor="w").pack(fill=tk.X, padx=10)

        # Rodapé discreto com autoria — empacotado antes do log para garantir visibilidade
        self.footer_label = tk.Label(
            self.root,
            text="Desenvolvido por Lucca Sarrassini",
            anchor="e",
            font=("Segoe UI", 9),
            fg="#333333",
        )
        self.footer_label.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 6))

        self.log_text = scrolledtext.ScrolledText(self.root, width=72, height=16, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, padx=10, pady=(4, 10), expand=True)

    def selecionar_arquivo(self):
        caminho = filedialog.askopenfilename(
            title="Selecione a planilha Excel",
            filetypes=[("Planilhas Excel", "*.xlsx *.xls"), ("Todos os arquivos", "*.*")],
        )
        if caminho:
            self.arquivo_selecionado.set(caminho)
            self._log(f"Arquivo selecionado: {caminho}")

    def iniciar_consulta(self):
        caminho = self.arquivo_selecionado.get().strip()
        if not caminho:
            messagebox.showwarning("Atenção", "Selecione um arquivo de entrada antes de iniciar a consulta.")
            return

        if not os.path.exists(caminho):
            messagebox.showerror("Erro", "O arquivo selecionado não existe.")
            return

        self.btn_iniciar.config(state=tk.DISABLED)
        self.progress.config(mode="determinate", value=0)
        self.progress_label.config(text="0/0 IPs processados")
        self._log("Iniciando consulta em segundo plano...")

        thread = threading.Thread(target=self._executar_consulta, args=(caminho,), daemon=True)
        thread.start()

    def _executar_consulta(self, caminho):
        try:
            arquivo_saida = processar_planilha(
                caminho,
                logger=self._thread_safe_log,
                progress_callback=self._thread_safe_progress,
            )
            self.root.after(0, lambda: messagebox.showinfo("Concluído", f"Consulta finalizada.\nArquivo salvo em:\n{arquivo_saida}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Falha durante o processamento:\n{e}"))
            self._thread_safe_log(f"Erro: {e}")
        finally:
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.btn_iniciar.config(state=tk.NORMAL))

    def _log(self, mensagem):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, mensagem + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _thread_safe_log(self, mensagem):
        self.root.after(0, lambda: self._log(mensagem))

    def _thread_safe_progress(self, current, total):
        self.root.after(0, lambda: self._set_progress(current, total))

    def _set_progress(self, current, total):
        if total <= 0:
            self.progress.config(value=0, maximum=100)
            self.progress_label.config(text="0/0 IPs processados")
            return

        self.progress.config(maximum=total, value=current)
        self.progress_label.config(text=f"{current}/{total} IPs processados")


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = App(root)
        root.mainloop()
    except Exception as e:
        print(f"Erro ao iniciar a interface: {e}")
        print("\nTente instalar o Tkinter:")
        print("Windows: pip install tk")
        print("Linux: sudo apt-get install python3-tk")
        print("macOS: brew install python-tk")
