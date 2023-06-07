from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame

class SpiTransactionFramer(HighLevelAnalyzer):
    """
    Merges SPI frames into transactions based on when the Enable line is active.
    """
    result_types = {
        "SpiTransaction": {
            "format": "COMMAND: {{data.command}}, MOSI: {{data.mosi}}, MISO: {{data.miso}}"
        },
        "SpiTransactionError": {
            "format": "ERROR: {{data.error_info}}",
        }
    }

    def __init__(self):
        # Holds the individual SPI result frames that make up the transaction
        self.frames = []

        # Whether SPI is currently enabled
        self.spi_enable = False

        # Start time of the transaction - equivalent to the start time of the "Enable" frame
        self.transaction_start_time = None

        # Whether there was an error.
        self.error = False

    def handle_enable(self, frame: AnalyzerFrame):
        self.frames = []
        self.spi_enable = True
        self.error = False
        self.transaction_start_time = frame.start_time

    def reset(self):
        self.frames = []
        self.spi_enable = False
        self.error = False
        self.transaction_start_time = None

    def is_valid_transaction(self) -> bool:
        return self.spi_enable and (not self.error) and (self.transaction_start_time is not None)

    def handle_result(self, frame):
        if self.spi_enable:
            self.frames.append(frame)

    def get_frame_data(self) -> dict:
        miso = bytearray()
        mosi_command = str()
        mosi = bytearray()

        for frame in self.frames:
            miso += frame.data["miso"]
            mosi += frame.data["mosi"]
            
            if frame.data["mosi"] == b'\xc0':
                mosi_command = "RESET"
            elif frame.data["mosi"] == b'\xa0':
                mosi_command = "READ STATUS"
            elif frame.data["mosi"] == b'\x03':
                mosi_command = "READ"    
            elif frame.data["mosi"] == b'\x05':
                mosi_command = "Bit Modify"  
            elif frame.data["mosi"] == b'\x02':
                mosi_command = "WRITE"  
            elif frame.data["mosi"] == b'\x81':
                mosi_command = "RTS TXB0" 
            elif frame.data["mosi"] == b'\x82':
                mosi_command = "RTS TXB1" 
            elif frame.data["mosi"] == b'\x84':
                mosi_command = "RTS TXB2"
            elif frame.data["mosi"] == b'\x40':
                mosi_command = "Load TX Buffer" 

        print()

        return {
            "miso": bytes(miso),
            "mosi": bytes(mosi),
            "command": mosi_command,
        }

    def handle_disable(self, frame):
        if self.is_valid_transaction():
            result = AnalyzerFrame(
                "SpiTransaction",
                self.transaction_start_time,
                frame.end_time,
                self.get_frame_data(),
            )
        else:
            result = AnalyzerFrame(
                "SpiTransactionError",
                frame.start_time,
                frame.end_time,
                {
                    "error_info": "Invalid SPI transaction (spi_enable={}, error={}, transaction_start_time={})".format(
                        self.spi_enable,
                        self.error,
                        self.transaction_start_time,
                    )
                }
            )

        self.reset()
        return result

    def handle_error(self, frame):
        result = AnalyzerFrame(
            "SpiTransactionError",
            frame.start_time,
            frame.end_time,
            {
                "error_info": "The clock was in the wrong state when the enable signal transitioned to active"
            }
        )
        self.reset()

    def decode(self, frame: AnalyzerFrame):
        if frame.type == "enable":
            return self.handle_enable(frame)
        elif frame.type == "result":
            return self.handle_result(frame)
        elif frame.type == "disable":
            return self.handle_disable(frame)
        elif frame.type == "error":
            return self.handle_error(frame)
        else:
            return AnalyzerFrame(
                "SpiTransactionError",
                frame.start_time,
                frame.end_time,
                {
                    "error_info": "Unexpected frame type from input analyzer: {}".format(frame.type)
                }
            )
