/** Read and decode a bounded UTF-8 stream; never buffer unbounded gateway bodies. */
export class BodyLimitExceeded extends Error {}
export async function readBoundedBody(body: ReadableStream<Uint8Array>|null, maxBytes: number): Promise<string> {
  if(!body)return "";
  const reader=body.getReader();
  const decoder=new TextDecoder("utf-8",{fatal:true});
  let count=0;
  const chunks:string[]=[];
  try {
    while(true){
      const {done,value}=await reader.read();
      if(done)break;
      count+=value.byteLength;
      if(count>maxBytes)throw new BodyLimitExceeded("Body exceeds limit");
      chunks.push(decoder.decode(value,{stream:true}));
    }
    chunks.push(decoder.decode());
    return chunks.join("");
  }catch(error){
    // Cancellation is best effort and must not mask the original failure.
    void reader.cancel().catch(()=>{});
    throw error;
  }finally{reader.releaseLock();}
}
