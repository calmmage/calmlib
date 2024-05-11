class App:
    def invoke(self, input_str: str) -> str:
        output_str = input_str
        return output_str

    def naive_run(self):
        while True:
            input_str = input()
            if input_str == 'exit':
                break
            print(self.invoke(input_str))

if __name__ == '__main__':
    app = App()

    app.naive_run()
