use std::future::Future;
use futures::TryFutureExt;

enum MySenderError<T> {
    AsyncChannel(async_channel::SendError<T>)
}

impl<T> From<async_channel::SendError<T>> for MySenderError<T> {
    fn from(value: async_channel::SendError<T>) -> Self {
        MySenderError::AsyncChannel(value)
    }
}

enum MyReceiverError {

}

trait Sender<'a, T> {
    type SendOutput: Future<Output=Result<(), MySenderError<T>>>;
    fn send(&self, msg: T) -> Self::SendOutput;
}

trait Receiver<T> {
    type RecvOutput: Future<Output=Result<T, MyReceiverError>>;
    fn recv(&self) -> Self:: RecvOutput;
}

impl<'a, T: 'a> Sender<'a, T> for async_channel::Sender<T> {
    type SendOutput = async_channel::Send<'a, T>;

    fn send(&self, msg: T) -> Self::SendOutput {
        self.send(msg)
    }
}